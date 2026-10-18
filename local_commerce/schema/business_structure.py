"""Remove only the former single-column Company uniqueness constraint."""
import frappe


def allow_shared_company():
    if not frappe.db.table_exists('LC Shop'):
        return
    indexes = frappe.db.sql('SHOW INDEX FROM `tabLC Shop`', as_dict=True)
    groups = {}
    for row in indexes:
        groups.setdefault(row.Key_name, []).append(row)
    for name, rows in groups.items():
        if (name != 'PRIMARY' and len(rows) == 1 and not rows[0].Non_unique
                and rows[0].Column_name == 'company'):
            # Identifier is database metadata, quoted independently of SQL values.
            identifier = name.replace('`', '``')
            frappe.db.sql(f'ALTER TABLE `tabLC Shop` DROP INDEX `{identifier}`')
