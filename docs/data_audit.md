# Source data and policy audit

The original challenge and all six input tables were inspected before implementation.
Original exports use the prefix `desafio_tecnico_ai_eng - ` rather than canonical filenames.
The loader accepts either convention and rejects directories containing both for a table.
All six source CSVs decode as UTF-8 (the reader also accepts a BOM). Values were inspected
with Python's CSV parser, Decimal conversion, JSON decoding, and relational validation.

| Table | Rows | Key | Relationships / types |
| --- | ---: | --- | --- |
| categories | 9 | category_id, positive integer | Name and description are text |
| products | 65 | product_id, positive integer | category_id → categories; decimal BRL → integer cents; stock integer; specs JSON object; creation ISO date |
| customers | 50 | customer_id, positive integer | Name, phone, email, city; contacts replaced in public fixtures |
| orders | 20 | order_id, positive integer | customer_id → customers; ISO dates; status/payment enum; historical BRL total → cents |
| order_items | 22 | (order_id, product_id) | Both foreign keys enforced; positive integer quantity |
| promotions | 25 | promotion_id, positive integer | product_id → products; integer percent; active boolean encoded as 0/1 |

No duplicate primary keys, duplicate complete rows, orphan foreign keys, negative stock,
or invalid JSON product specifications were observed. Every order has line items. No required
field is empty. `tracking_code` and `estimated_delivery` each have 12 empty values;
`notes` has 16. The loader converts these optional blanks to SQL NULL. It rejects missing
required values, malformed rows, unexpected columns, invalid status/payment enums and
invalid dates rather than silently fabricating replacements. Builds are atomic.

Products have 62 `active`, 2 `discontinued`, and 1 `coming_soon` records. Product 96 is active
but has zero stock; product 113 is discontinued with zero stock. Product 136 is discontinued
despite 13 units, and product 130 is coming soon despite 2 units. Availability therefore
requires **both active status and positive quantity**. Six of the nine category IDs occur
in the provided product subset. The manual mentions a catalogue of more than 300 instruments;
the application queries the actual 65-row subset and does not invent missing instruments.

Order dates range from 2025-10-15 to 2026-03-22. Status counts are delivered 7, shipped 1,
confirmed 4, pending 4, cancelled 4. Current catalogue sums disagree with recorded totals for
order 3 (R$3,450.00 recorded vs R$3,498.00 current items) and order 20 (R$1,400.00 vs R$1,488.00).
No historical unit price, promotion-at-purchase, shipping charge, or adjustment breakdown
exists. The reason for these differences is unknown. Recorded order totals remain authoritative;
the code does not "repair" them using current product prices.

Four promotions are marked active, for products 90, 94, 121 and 127. There are no campaign
date fields, so `is_active` is the only supplied applicability signal. Calendar events in the
manual do not activate campaigns. Product `price_brl` is interpreted as the list price;
active campaign percentages produce the effective price. In the hypothetical case of
multiple active campaigns on one product, the largest discount wins, never their sum.
Campaigns cannot be combined with the manual's 5% PIX discount. Prices are snapshot quotes.

The policy PDF has 8 pages, version 2.1, June 2025. Layout extraction preserves readable
tables; section parsing yields 29 chunks including the cover. Sections 5.2, 7.2 and 9 cross
page boundaries; chunks retain all source page numbers. Rules used include opening hours,
address, payment tiers, return conditions, shipping, promotion non-stacking, warranty and scope.
These are supplied store policies, not an independent statement of current legislation.

Ambiguities are surfaced rather than silently resolved:

- Section 1.2 gives phone/WhatsApp (67) 3341-4444; section 7 gives WhatsApp (67) 3321-4500.
  The cover and section 1.2 also differ in email spelling (accented vs unaccented domain).
  The assistant should state the conflicting source values and ask the team to verify contact details.
- The payment overview mentions R$100 minimum installments, while section 3.1 provides
  more specific tiers: up to 3 installments with the below-R$50 exception, 4–6 at R$80,
  7–12 at R$100. The quote tool conservatively interprets the exception as a R$50 minimum
  for 2–3 installments. Single payments have no installment minimum. Exact cent remainders
  are spread across installments and are shown, not hidden.
- Local freight is free **above** R$500 and R$35 **below** it; exactly R$500 is unspecified.
  The application does not select a fee at that boundary. It has no freight quotation API.
- Online regret is within 7 calendar days of actual receipt. Orders have only estimated
  delivery and no sales channel or actual receipt date. The assistant must ask for those facts.
  Seven elapsed calendar days is interpreted inclusively by the preliminary check.
- Preference-exchange timing has no clear reference event, and special-item exclusions may
  need case-specific review. The assistant escalates ambiguity and never automatically approves
  or denies legal rights. Warranty rules remain distinct from store exchange windows.
- Historical tracking examples do not consistently establish a validated carrier format.
  The tool returns the recorded value without asserting carrier validation; public fixtures
  replace it with a clearly marked `DEMO` value.

The public fixtures preserve catalogue facts, IDs, quantities, status, dates and monetary
values. All customer names, phones, emails and cities are synthetic replacements. Tracking
codes are synthetic, and free-text order notes are replaced by a generic cancellation note.
This avoids assuming that plausible-looking personal contacts in the source are fictitious.
Original CSVs are ignored before the first commit; the original challenge and academic PDFs
are also excluded. `scripts/prepare_public_data.py` reproduces the sanitized fixture from local
originals; a fresh clone already contains the sanitized data and does not require private files.
