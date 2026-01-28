"""
Contact exporter for iOS backups.

Parses the AddressBook database from iOS backups and exports
contacts to various formats including vCard (VCF).
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from orange.constants import APPLE_EPOCH_OFFSET
from orange.core.backup.reader import BackupReader
from orange.core.export.models import (
    Contact,
    ContactAddress,
    ContactEmail,
    ContactPhone,
)
from orange.exceptions import ExportError

logger = logging.getLogger(__name__)

# iOS AddressBook database location
ADDRESSBOOK_DB_DOMAIN = "HomeDomain"
ADDRESSBOOK_DB_PATH = "Library/AddressBook/AddressBook.sqlitedb"


class ContactExporter:
    """
    Exports contacts from iOS backups.

    Parses the AddressBook.sqlitedb database and exports contacts
    to JSON, CSV, or vCard (VCF) formats.

    Example:
        reader = BackupReader("/path/to/backup")
        exporter = ContactExporter(reader)

        # Get all contacts
        contacts = exporter.get_contacts()

        # Export to vCard
        exporter.export_vcf(contacts, Path("./contacts.vcf"))
    """

    def __init__(self, backup_reader: BackupReader):
        """
        Initialize contact exporter.

        Args:
            backup_reader: BackupReader instance for the backup.
        """
        self._reader = backup_reader
        self._db_path: Optional[Path] = None

    def _ensure_database(self) -> Path:
        """
        Extract and return path to AddressBook database.

        Returns:
            Path to the extracted database file.

        Raises:
            ExportError: If database cannot be extracted.
        """
        if self._db_path and self._db_path.exists():
            return self._db_path

        db_path = self._reader.extract_database(
            ADDRESSBOOK_DB_DOMAIN, ADDRESSBOOK_DB_PATH
        )
        if not db_path:
            raise ExportError(
                f"Could not extract AddressBook database from backup. "
                f"Make sure the backup contains "
                f"{ADDRESSBOOK_DB_DOMAIN}/{ADDRESSBOOK_DB_PATH}"
            )

        self._db_path = db_path
        return db_path

    def _parse_date(self, date_value: Optional[float]) -> Optional[datetime]:
        """Parse iOS timestamp to datetime."""
        if not date_value:
            return None

        try:
            # AddressBook uses seconds since Apple epoch
            unix_timestamp = date_value + APPLE_EPOCH_OFFSET
            return datetime.fromtimestamp(unix_timestamp)
        except (ValueError, OSError):
            return None

    def get_contacts(
        self,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Contact]:
        """
        Get contacts from the backup.

        Args:
            search: Search string to filter contacts by name.
            limit: Maximum number of contacts to return.

        Returns:
            List of Contact objects.
        """
        self._ensure_database()
        contacts: list[Contact] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query ABPerson table (main contact records)
            query = """
                SELECT
                    ROWID,
                    First,
                    Last,
                    Middle,
                    Prefix,
                    Suffix,
                    Nickname,
                    Organization,
                    Department,
                    JobTitle,
                    Birthday,
                    Note,
                    CreationDate,
                    ModificationDate
                FROM ABPerson
            """

            conditions: list[str] = []
            params: list[Any] = []

            if search:
                conditions.append(
                    "(First LIKE ? OR Last LIKE ? OR Organization LIKE ?)"
                )
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern, search_pattern])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY Last, First"

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, params)

            for row in cursor.fetchall():
                contact = self._parse_contact_row(row, conn)
                if contact:
                    contacts.append(contact)

            conn.close()

        except sqlite3.Error as e:
            raise ExportError(f"Failed to read contacts: {e}") from e

        return contacts

    def _parse_contact_row(
        self, row: sqlite3.Row, conn: sqlite3.Connection
    ) -> Optional[Contact]:
        """Parse a database row into a Contact object."""
        try:
            contact_id = row["ROWID"]

            contact = Contact(
                contact_id=contact_id,
                first_name=row["First"],
                last_name=row["Last"],
                middle_name=row["Middle"],
                prefix=row["Prefix"],
                suffix=row["Suffix"],
                nickname=row["Nickname"],
                organization=row["Organization"],
                department=row["Department"],
                job_title=row["JobTitle"],
                notes=row["Note"],
                created_date=self._parse_date(row["CreationDate"]),
                modified_date=self._parse_date(row["ModificationDate"]),
            )

            # Parse birthday if present
            if row["Birthday"]:
                contact.birthday = self._parse_date(row["Birthday"])

            # Load multi-value properties (phones, emails, addresses)
            self._load_multi_values(contact, conn)

            return contact

        except Exception as e:
            logger.debug(f"Failed to parse contact row: {e}")
            return None

    def _load_multi_values(
        self, contact: Contact, conn: sqlite3.Connection
    ) -> None:
        """Load phone numbers, emails, and addresses for a contact."""
        cursor = conn.cursor()

        # Get multi-value records for this contact
        cursor.execute("""
            SELECT
                mv.property,
                mv.label,
                mv.value,
                mvl.value as label_text
            FROM ABMultiValue mv
            LEFT JOIN ABMultiValueLabel mvl ON mv.label = mvl.ROWID
            WHERE mv.record_id = ?
        """, (contact.contact_id,))

        for row in cursor.fetchall():
            property_type = row[0]
            label = row[3] or self._get_default_label(row[1])
            value = row[2]

            if not value:
                continue

            # Property types in AddressBook:
            # 3 = phone, 4 = email, 5 = address, etc.
            if property_type == 3:  # Phone
                contact.phones.append(ContactPhone(
                    number=value,
                    label=self._clean_label(label),
                ))
            elif property_type == 4:  # Email
                contact.emails.append(ContactEmail(
                    email=value,
                    label=self._clean_label(label),
                ))

        # Load addresses separately (they have multiple parts)
        self._load_addresses(contact, conn)

    def _load_addresses(
        self, contact: Contact, conn: sqlite3.Connection
    ) -> None:
        """Load physical addresses for a contact."""
        cursor = conn.cursor()

        # Addresses are stored with multiple entries per address
        cursor.execute("""
            SELECT
                mv.UID,
                mve.key,
                mve.value,
                mvl.value as label_text
            FROM ABMultiValue mv
            JOIN ABMultiValueEntry mve ON mv.UID = mve.parent_id
            LEFT JOIN ABMultiValueLabel mvl ON mv.label = mvl.ROWID
            WHERE mv.record_id = ? AND mv.property = 5
        """, (contact.contact_id,))

        # Group by UID (each address has multiple entries)
        addresses: dict[int, dict[str, Any]] = {}
        for row in cursor.fetchall():
            uid = row[0]
            key = row[1]
            value = row[2]
            label = row[3]

            if uid not in addresses:
                addresses[uid] = {"label": label or "home"}

            # Map keys to address fields
            key_mapping = {
                "Street": "street",
                "City": "city",
                "State": "state",
                "ZIP": "postal_code",
                "Country": "country",
            }
            if key in key_mapping and value:
                addresses[uid][key_mapping[key]] = value

        # Create ContactAddress objects
        for addr_data in addresses.values():
            address = ContactAddress(
                street=addr_data.get("street"),
                city=addr_data.get("city"),
                state=addr_data.get("state"),
                postal_code=addr_data.get("postal_code"),
                country=addr_data.get("country"),
                label=self._clean_label(addr_data.get("label", "home")),
            )
            contact.addresses.append(address)

    def _get_default_label(self, label_id: Optional[int]) -> str:
        """Get default label name for built-in labels."""
        # iOS uses negative IDs for built-in labels
        labels = {
            -1: "mobile",
            -2: "home",
            -3: "work",
            -4: "main",
            -5: "home fax",
            -6: "work fax",
            -7: "pager",
            -8: "other",
        }
        return labels.get(label_id or 0, "other")

    def _clean_label(self, label: Optional[str]) -> str:
        """Clean up label string."""
        if not label:
            return "other"
        # Remove _$!<>!$_ markers used by iOS
        cleaned = label.replace("_$!<", "").replace(">!$_", "")
        return cleaned.lower()

    def get_contact(self, contact_id: int) -> Optional[Contact]:
        """
        Get a specific contact by ID.

        Args:
            contact_id: The contact's ROWID.

        Returns:
            Contact if found, None otherwise.
        """
        contacts = self.get_contacts()
        for contact in contacts:
            if contact.contact_id == contact_id:
                return contact
        return None

    def get_statistics(self) -> dict[str, Any]:
        """
        Get contact statistics.

        Returns:
            Dict with statistics including total contacts,
            phone count, email count, etc.
        """
        self._ensure_database()
        stats: dict[str, Any] = {
            "total_contacts": 0,
            "with_phones": 0,
            "with_emails": 0,
            "with_addresses": 0,
            "with_photos": 0,
        }

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            # Total contacts
            cursor.execute("SELECT COUNT(*) FROM ABPerson")
            stats["total_contacts"] = cursor.fetchone()[0]

            # Contacts with phones
            cursor.execute("""
                SELECT COUNT(DISTINCT record_id)
                FROM ABMultiValue WHERE property = 3
            """)
            stats["with_phones"] = cursor.fetchone()[0]

            # Contacts with emails
            cursor.execute("""
                SELECT COUNT(DISTINCT record_id)
                FROM ABMultiValue WHERE property = 4
            """)
            stats["with_emails"] = cursor.fetchone()[0]

            # Contacts with addresses
            cursor.execute("""
                SELECT COUNT(DISTINCT record_id)
                FROM ABMultiValue WHERE property = 5
            """)
            stats["with_addresses"] = cursor.fetchone()[0]

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not get statistics: {e}")

        return stats

    def export_json(
        self,
        contacts: list[Contact],
        output_path: Path,
        pretty: bool = True,
    ) -> Path:
        """
        Export contacts to JSON format.

        Args:
            contacts: List of contacts to export.
            output_path: Path for output file.
            pretty: Whether to format with indentation.

        Returns:
            Path to the created file.
        """
        data = {
            "export_date": datetime.now().isoformat(),
            "contact_count": len(contacts),
            "contacts": [c.to_dict() for c in contacts],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)

        logger.info(f"Exported {len(contacts)} contacts to {output_path}")
        return output_path

    def export_csv(
        self,
        contacts: list[Contact],
        output_path: Path,
    ) -> Path:
        """
        Export contacts to CSV format.

        Args:
            contacts: List of contacts to export.
            output_path: Path for output file.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                "First Name",
                "Last Name",
                "Organization",
                "Job Title",
                "Phone (Mobile)",
                "Phone (Home)",
                "Phone (Work)",
                "Email (Home)",
                "Email (Work)",
                "Address",
                "Birthday",
                "Notes",
            ])

            # Write contacts
            for contact in contacts:
                # Get primary values for each type
                mobile = next(
                    (p.number for p in contact.phones if "mobile" in p.label),
                    contact.phones[0].number if contact.phones else ""
                )
                home_phone = next(
                    (p.number for p in contact.phones if "home" in p.label),
                    ""
                )
                work_phone = next(
                    (p.number for p in contact.phones if "work" in p.label),
                    ""
                )
                home_email = next(
                    (e.email for e in contact.emails if "home" in e.label),
                    contact.emails[0].email if contact.emails else ""
                )
                work_email = next(
                    (e.email for e in contact.emails if "work" in e.label),
                    ""
                )
                address = (
                    contact.addresses[0].format_single_line()
                    if contact.addresses else ""
                )

                writer.writerow([
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.organization or "",
                    contact.job_title or "",
                    mobile,
                    home_phone,
                    work_phone,
                    home_email,
                    work_email,
                    address,
                    (contact.birthday.strftime("%Y-%m-%d")
                     if contact.birthday else ""),
                    contact.notes or "",
                ])

        logger.info(f"Exported {len(contacts)} contacts to {output_path}")
        return output_path

    def export_vcf(
        self,
        contacts: list[Contact],
        output_path: Path,
    ) -> Path:
        """
        Export contacts to vCard (VCF) format.

        Args:
            contacts: List of contacts to export.
            output_path: Path for output file.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        vcards: list[str] = []
        for contact in contacts:
            vcards.append(self._contact_to_vcard(contact))

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(vcards))

        logger.info(f"Exported {len(contacts)} contacts to {output_path}")
        return output_path

    def _contact_to_vcard(self, contact: Contact) -> str:
        """Convert a Contact to vCard 3.0 format."""
        lines = ["BEGIN:VCARD", "VERSION:3.0"]

        # Name
        name_parts = [
            contact.last_name or "",
            contact.first_name or "",
            contact.middle_name or "",
            contact.prefix or "",
            contact.suffix or "",
        ]
        lines.append(f"N:{';'.join(name_parts)}")

        # Full name
        lines.append(f"FN:{contact.display_name}")

        # Organization
        if contact.organization:
            org_parts = [contact.organization]
            if contact.department:
                org_parts.append(contact.department)
            lines.append(f"ORG:{';'.join(org_parts)}")

        if contact.job_title:
            lines.append(f"TITLE:{contact.job_title}")

        # Phones
        for phone in contact.phones:
            label = phone.label.upper()
            type_param = self._vcard_phone_type(label)
            lines.append(f"TEL;TYPE={type_param}:{phone.number}")

        # Emails
        for email in contact.emails:
            label = email.label.upper()
            type_param = "HOME" if "home" in label.lower() else "WORK"
            lines.append(f"EMAIL;TYPE={type_param}:{email.email}")

        # Addresses
        for addr in contact.addresses:
            label = addr.label.upper()
            type_param = "HOME" if "home" in label.lower() else "WORK"
            # ADR format: PO Box;Ext Addr;Street;City;State;Postal;Country
            addr_parts = [
                "",  # PO Box
                "",  # Extended address
                addr.street or "",
                addr.city or "",
                addr.state or "",
                addr.postal_code or "",
                addr.country or "",
            ]
            lines.append(f"ADR;TYPE={type_param}:{';'.join(addr_parts)}")

        # Birthday
        if contact.birthday:
            lines.append(f"BDAY:{contact.birthday.strftime('%Y-%m-%d')}")

        # Notes
        if contact.notes:
            # Escape special characters in notes
            escaped_notes = (
                contact.notes
                .replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace(",", "\\,")
            )
            lines.append(f"NOTE:{escaped_notes}")

        lines.append("END:VCARD")
        return "\n".join(lines)

    def _vcard_phone_type(self, label: str) -> str:
        """Map label to vCard phone type."""
        label_lower = label.lower()
        if "mobile" in label_lower or "cell" in label_lower:
            return "CELL"
        elif "home" in label_lower:
            return "HOME"
        elif "work" in label_lower:
            return "WORK"
        elif "fax" in label_lower:
            return "FAX"
        elif "pager" in label_lower:
            return "PAGER"
        else:
            return "VOICE"
