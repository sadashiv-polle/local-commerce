"""Opt-in statement/reminder queueing; shop mutex makes daily retries idempotent."""
import json
from html import escape
import frappe
from local_commerce.services.payments.accounting import posting
from local_commerce.services.payments.rules import money
from .commission_rules import signed_money


def daily():
    if not frappe.db.get_single_value('LC Store Settings','commission_reminders'):
        return
    today = frappe.utils.getdate()
    if today.day != 1 and today.weekday() != 0:
        return
    for name in frappe.get_all('LC Shop', filters={'gst_enabled':1}, pluck='name', limit_page_length=0):
        frappe.enqueue('local_commerce.services.gst.commission_mail.queue', shop=name, enqueue_after_commit=True)


def queue(shop):
    if not frappe.db.get_single_value('LC Store Settings','commission_reminders'):
        return
    from local_commerce.api.commissions import rows
    from .reports import csv_bytes
    today = frappe.utils.getdate()
    doc = frappe.get_doc('LC Shop',shop,for_update=True)
    if not doc.get('shop_email') or not doc.get('commission_customer'):
        return
    log = json.loads(doc.get('commission_dispatch_json') or '{}')
    periods = []
    if today.day == 1:
        end = frappe.utils.add_days(today,-1)
        start = frappe.utils.getdate(end).replace(day=1)
        periods.append(('statement:'+str(start)[:7],start,end,False))
    if today.weekday() == 0:
        periods.append(('overdue:'+str(today),frappe.utils.add_days(today,-365),today,True))
    with posting():
        for key,start,end,overdue in periods:
            if key in log:
                continue
            data = [r for r in rows(start,end,shop) if r['invoice'] and r['outstanding'] is not None]
            if overdue:
                data = [r for r in data if r['overdue']]
            if not data:
                continue
            due = sum((signed_money(r['outstanding']) for r in data),money(0))
            subject = ('Overdue commission reminder' if overdue else 'Monthly commission statement')+' — Local dot'
            frappe.sendmail(recipients=[doc.shop_email],subject=subject,
                message=f'<p>{escape(doc.shop_name)}</p><p>Commission invoice balance for the attached period: INR {due:.2f}.</p>'
                        '<p>This statement summarises existing invoices and does not create a new charge. View invoice and payment history in your shop’s Commission &amp; statements section.</p>',
                attachments=[{'fname':'commission-statement.csv','fcontent':csv_bytes(data)}],delayed=True)
            log[key] = str(today)
        # Keep a bounded history, including all current retry keys.
        log = dict(sorted(log.items(),key=lambda pair:pair[1])[-36:])
        frappe.db.set_value('LC Shop',shop,'commission_dispatch_json',json.dumps(log),update_modified=False)
