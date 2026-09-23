# ENG SPEC — Soft Personal interest form

**Status:** Eng unlocked (CoS 2026-09-22) · Copy CMO PASS (Wed Clip 3)  
**Brand:** Nerra Network only  
**SoT copy:** `WED-clip3-Personal-paste-for-CMO-QA.md` § Soft Personal · `IMPLEMENT-BRIEF-soft-personal-interest.md`  
**Not a fake waitlist.** `join.html` paid checkout stays secondary CTA.

---

## Placement (preferred → fallback)

1. **Preferred:** Dedicated lightweight page — `https://nerranetwork.com/personal-interest` (or `/personal` interest section) **or** a clear interest block **above** Stripe checkout on `join.html` (do not replace checkout).
2. **OK later:** Soft strip on SpaceX Daily episode pages (hero trail) — same copy; not required for v1.
3. **Do not:** Replace spoken Soft Personal end-sting (already live on SpaceX Daily) or imply the form is the only path.

Spoken audio already points people at Personal / join; form is the **email-only interest** path for people not ready to pay.

---

## Fields

| Field | Required | Notes |
|-------|----------|-------|
| Email | **Yes** | Valid email |
| First name | No | For Mira greeting later |
| Checkbox: “I’m interested in Nerra Personal” | Yes (UI) | **Default ON** |
| Checkbox: “I’d like the free SpaceX Daily / network newsletter too” | No | Default off |

---

## CTAs / buttons

- **Primary:** `Save my email`
- **Secondary (same screen, link):** `Or start Personal now →` → `https://nerranetwork.com/join.html`

---

## Header / body (exact)

**Header**
```
Your own morning show — when you’re ready
```

**Body**
```
All 18 Nerra shows stay free. Personal is optional: you pick the shows (SpaceX Daily included), Mira greets you by name, and one private podcast feed arrives in the app you already use.

Want a quiet nudge with Personal tips — or a reminder to try it when you’re ready? Leave your email. No ads. No outrage diet. Curiosity only.
```

---

## Success / error copy

**Success (exact)**
```
You’re on the list. Shows stay free either way. If you want Personal today, it’s one click from your account — cancel anytime.
```

**Error — invalid / empty email (Brand-safe; not in prior paste — proposed)**
```
That email doesn’t look right. Try again, or start Personal now at nerranetwork.com/join.
```

**Error — submit failed / network (proposed)**
```
Couldn’t save that just now. Try again in a moment — or start Personal whenever you’re ready at nerranetwork.com/join.
```

---

## Submit destination (preference order)

1. **Preferred:** **Buttondown** — patricknovak1 / Nerra Network list (same account as Ask C). Tag/segment: `personal-interest` (or equivalent). Optional second tag if newsletter checkbox: existing network newsletter segment.
2. **Acceptable alt:** Resend audience / contact with same tags if Buttondown wiring is harder this sprint.
3. **Avoid for v1:** Google Sheets as sole SoT (ok as eng debug mirror only).
4. **Do not** auto-charge or create a paid Personal subscription from this form.

No confirmation email required for v1 unless already trivial; if sent, keep voice (curiosity, optional, no scarcity).

---

## Must-nots

- Fake scarcity / “waitlist closing” / “spots left”
- Any **episode total** (frozen); avoid echoing `join.html` **1969+** strip
- FOMO / “you’re missing out” / anxiety framing
- Implying Personal is required or that free shows go away
- Blending Lil Words / Rel Copilot / Avvizo / Bill Saved
- Treating this as a closed waitlist while `join.html` checkout is live

**OK:** 18 shows · most daily · optional · coffee-a-month · one-click cancel · curiosity not anxiety

---

## QA before traffic

Brand HoM + portfolio CMO live-surface QA after eng ships; then Patrick traffic/spend if any.

---

## Doc index

| Doc | Path |
|-----|------|
| This eng spec | `campaigns/ENG-SPEC-soft-personal-interest-form.md` |
| Implement brief | `campaigns/IMPLEMENT-BRIEF-soft-personal-interest.md` |
| CMO PASS copy | `campaigns/WED-clip3-Personal-paste-for-CMO-QA.md` |
| CMO QA note | `campaigns/CMO-QA-WED-clip3-Personal.md` |
| Strategy (Buttondown preference) | `strategy/growth-next-move-draft.md` § Option B |
