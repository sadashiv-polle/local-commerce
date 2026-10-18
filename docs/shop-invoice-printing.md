# Local dot shop invoice printing

This release reuses submitted ERPNext Sales Invoices. It does not create a second
invoice or change the legal supplier, numbering, taxes, amounts or accounting.

## What users see

Orders with an issued invoice have **Download shop invoice**. The PDF shows the
Local dot logo, saved shop name, legal supplier and the standard ERPNext invoice
body. The existing 80 mm **Print receipt** remains a separate order summary.

Customers can download invoices for their own orders. Shop members need access
to the specific shop; being in the same Company does not grant access to another
shop's invoices. Delivery assignment alone does not grant invoice download access.

## Where the invoice is saved

The original Sales Invoice remains the financial record, linked by `lc_order`.
New invoices also store `lc_shop` and `lc_shop_name`, so an administrator can filter
Sales Invoices by **Local Commerce Shop**. Renaming a shop does not change a saved
invoice's brand. Credit notes inherit the original attribution.

Older invoices are not rewritten. Their print header uses the current shop name;
the original supplier and financial values still come from the saved invoice.
The shop invoice listing endpoint joins through the order link to include these
older records.

## Install on an existing bench

After taking a site backup, pull `main`, build the frontend, migrate the site,
clear its cache and restart the bench. Migration installs the print format and the
two read-only Sales Invoice fields. The server's normal ERPNext PDF generator is
required. Test one shop invoice, its customer download and a cross-shop access
attempt after deployment.

## Scope

This print release does **not** enable the single-company third-party-vendor
accounting model. Its development branch still needs the vendor-payable,
settlement, refund and inventory-accounting implementation and staging validation.
It does not reclassify vendor revenue or migrate existing Companies.

The confirmed target arrangement is that third-party shops are the sellers of
their goods; Shiv Tech Works earns marketplace commission. Restaurant Section
9(5) invoicing continues through the existing separate GST document workflow.
The branded PDF is not a substitute for configuring the correct legal supplier,
GST details or India Compliance requirements in the underlying ERPNext invoice.
