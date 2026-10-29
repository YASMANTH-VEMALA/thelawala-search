# Thelawala: email thread on search

---

**From:** Kavya (Founder)
**Subject:** Search

Team, search is our biggest leak. Our customers don't type the way our catalog is written. They type the way they talk, and they're on a phone with one thumb. Search should understand them. Think Google, not Ctrl+F.

---

**From:** Sandeep (Operations Lead)

Two things from the warehouse side.

First, please never show products we can't deliver. When a customer orders something that's out of stock and we cancel it later, that's a 1-star review.

Second, try searching "milk" today. The first results aren't even milk. It's embarrassing.

---

**From:** Farah (Category Manager)

Sandeep, I disagree on stock. If we hide out-of-stock items, the customer thinks we don't sell them and goes to a competitor. Show them, with when they're back.

Thela Select is our own label and our best margin. It should come first wherever we have it.

The search log is gold. It shows exactly what customers want. The most-clicked products should be at the top.

Also, customers type things like "oil under 200". It would be great if that worked.

---

**From:** Kavya (Founder)

I don't want us to be pushy. If someone searches for a brand, show them that brand. Customer first, margin second.

---

**From:** Arjun (Tech Lead)

Constraints from my side:

- **No external API calls at search time.** Latency and per-query cost both matter at our volume.
- **It has to run on an ordinary laptop-class server.**
- **The catalog changes every day** (new products, price updates), so whatever you build can't depend on someone hand-editing things.
- **Volume:** we're at around 1,100 products and expect 20,000 by next year.
- **Keep it to a single search box for now.** No filter UI.

---

**From:** Sandeep (Operations Lead)

Unrelated, maybe: a couple of customers complained last week that some prices in the app looked wrong. Finance is looking into it.
