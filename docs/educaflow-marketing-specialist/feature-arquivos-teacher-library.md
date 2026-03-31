# Feature brief: Arquivos (teacher library)

**Product:** EducaflowOne  
**In-app name (PT-BR):** Arquivos — *“Sua biblioteca de materiais”*  
**Route:** `/arquivos/`  
**Audience for this doc:** marketing / growth agent formulating campaigns, emails, landing sections, and upgrade narratives.

---

## 1. Elevator pitch (English)

**Arquivos** is a **built-in personal library** for each teacher: PDFs, audio, video, images, office documents, and **saved links**—organized with search, filters, and tags. Teachers reuse materials across students without digging through chat history or random folders. **One action** pushes a **copy** of a file to a specific student’s materials (student portal), so sharing stays controlled and traceable inside the product.

Differentiator: it is **not** generic cloud storage—it sits **next to calendar, students, and planning**, with **subscription-aware limits** and a path to the **student-facing area**.

---

## 2. Problem it solves

| Pain | How Arquivos helps |
|------|---------------------|
| Materials scattered across Drive, WhatsApp, email, desktop | One library **inside the same tool** they use to run the business |
| Re-sharing the same PDF to many students over time | Upload once; **send to student** creates a proper student record |
| Losing uploads when a host resets servers (ops reality) | Production stack supports **durable object storage** (e.g. Cloudflare R2) so files are not tied to a fragile container disk |
| “Tasks” board unused; planning already covers scheduling | Legacy **Tasks / Tarefas** removed; **Arquivos** takes the nav slot with clearer value |

---

## 3. Core user stories (copy-ready)

- *“I want my worksheets, audio tracks, and course PDFs in one place tied to my account.”*  
- *“I want to tag and find materials quickly before class.”*  
- *“I want to send this file to **Ana** without re-uploading from my laptop each time.”*  
- *“I want to save a YouTube or article link as a resource, not only files.”*

---

## 4. What the teacher can do (feature list)

- **Upload files** (multipart upload with progress).  
- **Add link-type materials** (external URL).  
- **Title, description, tags** (description is teacher-internal positioning; confirm UX if customer-facing claims differ).  
- **Search and filter** (including by type and tag).  
- **Storage meter** relative to plan limits (reduces surprise upgrades / support tickets).  
- **Edit** metadata and link URL; **delete** (removes stored file when applicable).  
- **Send to student:** picks an **active** student; creates a **separate** `StudentMaterial` copy (not a live symlink—student gets their own record for the portal).  
- **Download** via authenticated app flow (important for non-public media URLs in production).

---

## 5. Relationship to “Área do Aluno” / student materials

- **Student materials** already existed: tied to **one student**, visible in the student area.  
- **Teacher library** is **account-wide**.  
- **Bridge:** “Send to student” = one-way handoff into the student’s material list.  
- **Marketing angle:** “From your library to your student’s portal in one step.”

---

## 6. Plans and limits (facts for pricing pages & email)

Tier logic comes from the live product (`Subscription.get_arquivos_limits()`). Use **rounded** numbers in marketing copy unless legal requires exact bytes.

| Tier | Max single file | Total library size (approx.) | Max number of files |
|------|-----------------|------------------------------|---------------------|
| **Basic** | 10 MB | 100 MB | 50 |
| **Premium** | 20 MB | 500 MB | 200 |
| **Platinum** | 50 MB | ~2 GB | **Unlimited** (no numeric cap in product) |
| **Trial / no paid subscription** | Same as Basic-equivalent defaults | Same as Basic-equivalent | Same as Basic-equivalent |

**File types allowed (illustrative, not exhaustive in ads):** PDF, Word/Excel/PowerPoint, common audio (e.g. MP3), video (e.g. MP4, WebM), images (JPEG, PNG, GIF, WebP), TXT—aligned with backend allow-lists.

**Upgrade narrative examples (English):**  
- *“Hitting your 100 MB library cap? Premium unlocks 500 MB and bigger uploads.”*  
- *“Platinum removes the file count ceiling for power users with large repertoires.”*

---

## 7. Who does **not** see this (guardrails)

- **Partner teachers** (accounts configured as “partner” in the product): **Arquivos is blocked** (API 403; UI redirects).  
- **Do not** promise “every seat gets Arquivos” without checking partner-mode positioning. If partners are a segment you mail, segment the list or omit the feature for them.

---

## 8. Positioning vs alternatives

| Alternative | Contrast |
|-------------|----------|
| Google Drive / Dropbox | Arquivos is **inside the tutoring OS**—next to roster and calendar, with **student handoff** to the portal |
| WhatsApp as file vault | Searchable, tagged, quota-aware, not mixed with chat noise |
| LMS-heavy products | Lighter than a full LMS; fits **1:1 and small studio** private tutors |

Avoid claiming “unlimited storage” globally—**only Platinum** drops the **file count** limit; total size still has a **2 GB** ceiling in code for that tier unless product changes.

---

## 9. Campaign & channel ideas (starters)

**Product launch / in-app announcement**  
- Headline: *Your teaching drawer, inside EducaflowOne.*  
- CTA: Open **Arquivos** → upload three recurring PDFs → send one to a student.

**Lifecycle email (existing customers)**  
- Segment: active payers, not partner-only.  
- Subject lines (A/B): *Stop hunting for last month’s worksheet* / *One library. Every student.*  
- Body: 3 bullets (one place, send to student, limits by plan) + link to `/arquivos/`.

**Upgrade campaign**  
- Trigger concept: user at **>80%** storage bar (if analytics exist) or hits upload limit (support ticket pattern).  
- Message: tie to **Premium/Platinum** limits table above.

**Blog / SEO (EN or PT)**  
- *How private tutors can organize reusable materials without another subscription*  
- *Why a student portal beats “I’ll WhatsApp you the PDF”*

**Social proof requests**  
- Ask beta teachers: *“What was the first file you put in Arquivos?”*

---

## 10. Tone & compliance notes

- **Trust:** files are serious data; prefer language about **control**, **your library**, **send when you choose**.  
- **Accuracy:** descriptions/tags are **teacher-side**; verify before saying “students see your internal notes.”  
- **Infrastructure:** optional to mention **durable cloud storage** as reliability—avoid vendor names unless comms strategy wants Cloudflare R2 explicit.  
- **Portuguese customer copy:** UI strings remain PT-BR; this brief is EN so the marketing agent can produce EN-first or then localize.

---

## 11. Cross-links (internal)

- Engineering / QA: `docs/educaflow-codebase-expert/arquivos-implementation-summary.md`, `arquivos-feature-plan.md`  
- Deploy / static + media stability: `docs/educaflow-codebase-expert/incident-2026-03-staticfiles-r2-production.md` (why production file hosting matters for credibility)

---

*Last updated: 2026-03-25 — aligned with shipped Arquivos + subscription limits in codebase.*
