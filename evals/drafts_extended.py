"""Hand-written emails for the corpus extension (evals/corpus_ext.py).
Same vagueness rules as drafts.py. Realism deliberately includes signatures,
disclaimers, ticket ids, forwards, replies in thread, typos, and one non-English report.
"""

EXTENDED: dict[tuple[str, int], tuple[str, str]] = {
    # INC-16 file-storage, signed-URL 403 (Sep 8) -----------------------------
    ("INC-16", 0): (
        "Nothing will open",
        "Second time this month I'm writing in. Since about 20 minutes ago none of the links to our stored files work, every single one gives a 'you don't have permission' page even for things I put there myself yesterday. Nothing changed on our side.\n\nDana Whitfield\nOperations, Acme Corp\n+1 415 555 0142",
    ),
    ("INC-16", 1): (
        "All object GETs returning 403 since ~05:40 UTC",
        "Hi,\n\nEvery signed download URL we generate is returning 403 with body:\n\n  {\"error\":\"SignedUrlError\",\"detail\":\"signature mismatch\"}\n\nThis includes URLs minted seconds ago. Uploads (PUT) still succeed. Started around 05:40 UTC based on our error dashboards. We have ~1,900 users hitting this.\n\nMiles Dyson\nCyberdyne - Platform\n\nThis email and any attachments are confidential and intended solely for the addressee.",
    ),
    # INC-17 notifications, push 401 (Sep 8) ----------------------------------
    ("INC-17", 0): (
        "Phone notifications stopped",
        "Hi,\n\nSince last night nobody on my team is getting the phone notifications anymore. The emails still come through, it's just the phone ones that stopped. We haven't changed any settings. Can you check?\n\nThanks,\nWilly\nWonka & Co",
    ),
    # INC-18 billing-api, annual preview (Sep 8) -------------------------------
    ("INC-18", 0): (
        "Can't upgrade - error on the plan page",
        "Hello,\n\nI'm trying to move us from the annual Pro plan to Business and when I click to see the new price the page shows 'Something went wrong, please try again' every time. I've tried Chrome and Safari. We want to add people before Monday.\n\nMichael Bluth\nBluth Company",
    ),
    ("INC-18", 1): (
        "your site is broken",
        "Can't change our plan. Error every time. Please fix.\n\nR. Angier",
    ),
    ("INC-18", 2): (
        "Re: Quote Q-48812 - unable to proceed",
        "Dear Support,\n\nWith reference to quote Q-48812, we attempted to accept the proposed terms via the account portal this morning and were met with an error message at the confirmation step. We have attempted this three times over the course of an hour with the same result. Kindly advise how we may proceed, as our procurement window closes Friday.\n\nYours faithfully,\nFleur Delacour\nProcurement, Gringotts\n\n--\nThis message may contain confidential information.",
    ),
    # INC-19 web-bff, blank page after login (Sep 9) ---------------------------
    ("INC-19", 0): (
        "Blank screen after signing in - widespread",
        "Hi team,\n\nWe have at least forty internal tickets in the last half hour. People sign in fine and then get a completely white screen, nothing loads, no error. Refreshing doesn't help. Phone app seems OK. Is there a status page we can point people to?\n\nNate Kwan\nSupport Lead, Hooli\nTicket ref: HOOLI-55120",
    ),
    ("INC-19", 1): (
        "white page",
        "tried on my laptop this time instead of the phone and it's just a white page after I log in. phone is fine. what's going on\n\n-jake",
    ),
    ("INC-19", 2): (
        "Re: Blank screen after signing in - widespread",
        "Update: it's now over a hundred tickets. One user sent a screenshot - the top bar loads, then everything under it stays white. Some people say it eventually loads after 30-40 seconds. Let me know if you want the screenshot.\n\nNate\n\nOn Wed, Sep 9, 2026 at 8:18 AM Nate Kwan wrote:\n> We have at least forty internal tickets in the last half hour. People sign in fine and then get a completely white screen.",
    ),
    ("INC-19", 3): (
        "Fwd: Stark Media - web app not loading",
        "Forwarding from my customer, they're a large account. Can someone take a look today?\n\nThanks,\nMaria Hill\nAccount Manager\n\n---------- Forwarded message ---------\nFrom: Tony <tony@stark.example.com>\nSubject: web app not loading\n\nMaria - the web app has been dead for us since this morning. Login works, then nothing. Our whole editorial team is sitting around. Is this known?\nTony",
    ),
    # INC-20 search-indexer lag (Sep 9) ---------------------------------------
    ("INC-20", 0): (
        "Search is slow to catch up",
        "Hey again! Different thing this time. When we add something new it takes ages before it shows up when you look for it - like 15 or 20 minutes. It used to be pretty much instant. Not urgent but people keep asking me.\n\nPam\nDunder Mifflin",
    ),
    # INC-21 payments-gateway refunds (Sep 9) ----------------------------------
    ("INC-21", 0): (
        "Can't give a customer their money back",
        "Hi,\n\nI've been trying all afternoon to send money back to a customer who cancelled and every time I click the button it fails with a red message. The customer has called twice now. Is there a problem on your end?\n\nThank you,\nArt Vandelay\nVandelay Industries",
    ),
    ("INC-21", 1): (
        "Refund failing for duplicate order",
        "Hello,\n\nOne of our clients was billed twice for the same matter and I'm trying to issue a refund for the duplicate. The refund fails each time with 'processor error'. The original charge went through fine. Order ref 88213-B.\n\nBest,\nHarriet Lowe\nParalegal, Wayne & Associates",
    ),
    # INC-22 sso-gateway OIDC discovery (Sep 10) -------------------------------
    ("INC-22", 0): (
        "SSO down for Initech only?",
        "Hello,\n\nSince roughly 08:00 UTC our users cannot sign in via single sign-on. Clicking the SSO button spins for about 30 seconds and then shows a generic error. Our identity provider (Okta) shows no failed logins, so the request never reaches it. Our one password-login admin account works. Did something change with how you fetch our IdP configuration?\n\nRegards,\nMei Lin\nEngineering Manager, Initech",
    ),
    # INC-23 reports-api decimal (Sep 10) --------------------------------------
    ("INC-23", 0): (
        "Report totals slightly off",
        "Hi,\n\nThe totals in our saved reports are a few cents off compared to what they were yesterday. For example the September revenue report shows 48,213.99 where our own spreadsheet has 48,214.00. It's small but finance noticed. Started today as far as I can tell.\n\nThanks,\nRichard Hendricks\nPied Piper",
    ),
    ("INC-23", 1): (
        "\"Monthly Spend by Vendor\" report: totals disagree with detail rows",
        "Hello,\n\nIn the saved report \"Monthly Spend by Vendor\" the footer total reads 1,204,318.71 but summing the detail rows gives 1,204,318.80. Yesterday both were 1,204,318.80. Two other currency reports show the same one-to-nine-cent discrepancy. Please advise.\n\nCave Johnson's office\nAperture Science, Accounts Payable",
    ),
    # INC-24 mobile-bff Android 15 (Sep 12) ------------------------------------
    ("INC-24", 0): (
        "app crashes",
        "got a new phone and now the app closes itself the second i open it. worked fine on my old one. same login.\n\n-jake, umbrella",
    ),
    ("INC-24", 1): (
        "Android app crash on launch - only after OS update",
        "Hi team,\n\nNew batch of tickets: Android users who updated to the latest OS version this week say the app crashes immediately on launch. Users on the previous OS version are fine, iOS is fine. Reinstalling doesn't help.\n\nNate Kwan\nSupport Lead, Hooli\nTicket ref: HOOLI-55307",
    ),
    # INC-25 exports-renderer PDF (Sep 12) -------------------------------------
    ("INC-25", 0): (
        "PDF exports are blank",
        "Hi support,\n\nSince this afternoon our PDF exports open as blank pages - the right number of pages, but nothing on them. The CSV export of the same report is fine. Can you look? We send these to clients.\n\nThanks,\nPriyanka Rao\nSenior Analyst, Northwind",
    ),
    ("INC-25", 1): (
        "Empty documents",
        "I just sent a client a document generated from your system and it was completely empty. Every page. This is embarrassing. Please tell me what happened.\n\nJoan Holloway\nSterling Cooper",
    ),
    # INC-26 session-store failover (Sep 13) -----------------------------------
    ("INC-26", 0): (
        "Everyone kicked out at 04:02",
        "At 04:02 UTC every single person in our org was thrown out at the same time and had to sign back in. Some people got an error on the first try. It seems OK now but I need to know what happened - was this on your side?\n\nGreg Tannen\nIT Administrator, Globex",
    ),
    ("INC-26", 1): (
        "lost my work",
        "I got kicked to the sign in screen out of nowhere in the middle of typing and lost twenty minutes of work. This is the second time this week something like this has happened.\n\nWalter\nMassive Dynamic",
    ),
    ("INC-26", 2): (
        "Mass sign-out - security incident?",
        "Hi,\n\nAll of our users were signed out simultaneously a little after 04:00 UTC. Before I escalate internally: was this a security event (credential reset, breach response) or an operational issue? We need to file an internal report either way.\n\nThanks,\nJune Harper\nIT, Veridian Dynamics",
    ),
    # INC-27 dashboard-api zeros (Sep 13) --------------------------------------
    ("INC-27", 0): (
        "Everything shows zero",
        "All the numbers on the first screen say 0 this morning. Has our data been deleted?? The detail pages still have everything. Please confirm nothing is lost.\n\nRobert Angier\nPrestige",
    ),
    # INC-28 auth-service reset TTL (Sep 13) -----------------------------------
    ("INC-28", 0): (
        "Password reset link says expired",
        "Hi, I forgot my password and requested a reset. The email arrives right away but when I click the link it says the link has expired, even if I click it within a minute. Tried three times. I have a demo at 11.\n\nDeckard\nSoylent",
    ),

    # ---- ungrounded ------------------------------------------------------------
    # INC-29 invoice-worker wrong name (Sep 8)
    ("INC-29", 0): (
        "Company name wrong on invoice",
        "Hello,\n\nOur invoice for August arrived this morning and the header shows \"Ollivanders Wand Co\" rather than our registered legal name \"Ollivanders Ltd\". Previous invoices were correct. Could you reissue it? Our auditors are strict about this.\n\nKind regards,\nGarrick",
    ),
    # INC-30 exports-scheduler duplicates (Sep 9)
    ("INC-30", 0): (
        "Scheduled exports running twice",
        "Hi,\n\nFor the last two mornings our scheduled exports have produced two files each instead of one - identical content, same timestamp to the second. Not a big problem but our downstream import chokes on the duplicate.\n\nThanks,\nPriyanka Rao\nNorthwind",
    ),
    ("INC-30", 1): (
        "duplicates every morning",
        "Every morning now there are two of everything in the folder. Same thing twice. Started a couple of days ago.\n\nMark S.\nLumon",
    ),
    # INC-31 notifications delayed (Sep 10)
    ("INC-31", 0): (
        "late",
        "the emails when someone @'s me are showing up like 3 hours late, is that normla?",
    ),
    # INC-32 web-bff side menu (Sep 10)
    ("INC-32", 0): (
        "Can't reach the save button",
        "Hi! Since the new look launched, on my laptop the menu on the left side sits on top of the page and covers the button at the bottom I need to press to save. If I zoom out a lot I can get to it. It's fine on the big monitor.\n\nPam\nDunder Mifflin",
    ),
    # INC-33 dashboard-api slow (Sep 12)
    ("INC-33", 0): (
        "First page very slow",
        "Hello,\n\nWhen I sign in, the first page takes about eight seconds to appear (I counted). Once I click into anything else it's instant. It's been like this since yesterday.\n\nMichael Bluth\nBluth Company",
    ),
    ("INC-33", 1): (
        "Slow landing page",
        "The page you land on after login is really slow for everyone here, 5-10 seconds. Everything else is fast. Not blocking but annoying dozens of times a day.\n\nWilly\nWonka & Co",
    ),
    # INC-34 billing-api VAT on receipts (Sep 12)
    ("INC-34", 0): (
        "Re: VAT on invoices",
        "Following up on my earlier question - the receipts we download from the billing page now show a VAT line, thank you, but our VAT registration number isn't printed anywhere on them. Finance needs it on the document itself.\n\nMiles Dyson\nCyberdyne",
    ),
    # INC-35 search-indexer deleted items (Sep 13)
    ("INC-35", 0): (
        "Deleted things keep coming back",
        "Hi,\n\nItems we deleted days ago still show up when you look for them by name. Clicking them gives 'not found', which is right, but they shouldn't appear at all. Confusing our users and it looks like a data-retention problem.\n\nBill Weasley\nGringotts",
    ),
    # INC-36 mobile-bff login every launch (Sep 13, Spanish)
    ("INC-36", 0): (
        "La aplicación pide iniciar sesión cada vez",
        "Hola,\n\nDesde ayer la aplicación del móvil me pide usuario y contraseña cada vez que la abro, aunque acabe de cerrarla. En el ordenador no pasa. ¿Es un problema conocido?\n\nGracias,\nLucía Ortega\nVeridian Dynamics (Madrid)",
    ),
    # INC-37 sso-gateway SCIM (Sep 12)
    ("INC-37", 0): (
        "New hires not appearing - SCIM provisioning",
        "Hi,\n\nThree employees who started Monday were added to the SSO group in our IdP but still don't show up on your side and can't sign in. Provisioning has been automatic for us for two years. Existing users are fine. Was something changed with group sync?\n\nGreg Tannen\nIT Administrator, Globex",
    ),
}
