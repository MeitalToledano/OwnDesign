# Overview

Source: `Interior_Design_AI_PRD_EN.md`, `README.md`.

A multi-tenant web platform where an interior design studio invites clients, and the client and
designer work on the same floor plan. AI assistance comes in later phases.

## Built: Phase 1

- A designer signs up and opens a studio. One studio per owner.
- A client enters through the studio link, a personal invite link, or as a guest. The client portal
  (`entry.html`) offers guest or account access, and the wizard or a blank canvas as a starting point.
- A guided wizard builds the apartment from rooms and dimensions.
- A 2D editor (SVG): walls, partitions, doors, windows, generic furniture, undo/redo, pan/zoom, keyboard use.
- Every save adds an immutable version tagged `client` or `designer`.
- A guest's plan stays in the browser until they register and save.
- The studio dashboard (`studio.html`) shows metrics, project cards with a plan thumbnail, search,
  the studio link, invites and recent activity.
- One studio cannot see another studio's data ([security.md](security.md)).

## Built: Phase 2

- Design brief per project: styles (up to 5), colours, budget range and currency, household, lifestyle,
  needs, fixed constraints, existing items to accommodate (`design.html`).
- Finish selections per room and surface (floor, walls, ceiling, cabinets) from a fixed catalog of styles
  and materials.
- Inspiration and existing-item images (JPEG, PNG, WebP, 5 MB, 30 per project) in private storage, shown
  through short-lived signed URLs, and a moodboard of images, styles and materials with notes and order.
- AI consultant (`consultant.html`): OpenAI `gpt-5-mini`, answers from the project's brief, finishes and
  plan summary, recommends only and never edits the plan. One private conversation per user and project,
  30 messages per user per day.
- The client and the studio's designers see the same brief, finishes and moodboard; the conversation is
  private to the user who held it.

## Built: furniture-layout suggestions (2026-11-26, not yet run against a live database)

- In the editor of a saved project, selecting a room shows "Suggest a layout". The client (or a studio designer)
  confirms a furniture list prefilled from the room type (the room's existing pieces are listed and can be
  unticked), and chooses whether the existing pieces stay put or may be moved. Up to 20 pieces.
- The AI (OpenAI) returns up to three layouts. The backend checks each one: inside the room, no overlaps, 90 cm
  kept clear in front of doors, exactly the requested pieces. Invalid layouts are dropped.
- The layouts show as thumbnails; the chosen one is drawn dashed on the plan. Apply adds an undo step; saving
  makes a version as usual. Cancel and Try again leave the plan alone. 10 requests per user per day.
- When the AI gives nothing usable (the call fails, the answer is unreadable, or every layout breaks a rule),
  standard placement rules answer instead, marked "Standard rules" in the editor. Without an OpenAI key the rules
  answer alone and no daily request is used.
- Wizard presets now come with a door (south wall) and a window (north wall), and there is a Kids Room preset.

## Not built yet

Renderings, budget, dossier,
messaging and tasks, studio branding, invitation emails, per-project team permissions, deployment,
rate limiting, subscriptions and credits.

## Next

Per the PRD: renderings, version comparison, budget and shopping list, dossier and handoff, messaging and
tasks, studio branding ([open-items.md](open-items.md) lists what must be settled before production).
