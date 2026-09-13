"""Hand-written customer emails for the corpus, keyed by (incident id, index).

Written to the same vagueness rules the model generator uses:
  high   — symptom only; no feature, service, endpoint, or error names
  medium — may name the feature
  low    — may include an endpoint, status code, or error text
"""

DRAFTS: dict[tuple[str, int], tuple[str, str]] = {
    # INC-01 exports-scheduler ------------------------------------------------
    ("INC-01", 0): (
        "Nothing has come through since this morning",
        "Hi,\n\nThe files we get every morning at 6 haven't shown up today. The little spinner on the page just keeps going and nothing lands in the folder. We have a board meeting at 11 and need these.\n\nCan someone look?\n\nDana Whitfield\nOperations, Acme Corp",
    ),
    ("INC-01", 1): (
        "is something broken?",
        "Hi there! I set up my weekly thing to run this morning and it never did, and when I try to kick it off by hand the button just sits there spinning. Not the end of the world but wanted to flag it :)\n\nCheers,\nRosa\nBrightline Studio",
    ),
    ("INC-01", 2): (
        "Re: scheduled exports not running",
        "Hi support,\n\nFollowing up on the below. Our scheduled exports didn't fire this morning and manual export attempts hang with a spinner. No error message, it just never completes. Started sometime between 5 and 7am our time.\n\nThanks,\nPriyanka Rao\nSenior Analyst, Northwind\n\nOn Thu, Sep 11, 2026 at 7:12 AM Tom Hale wrote:\n> Priyanka, the exports didn't come through again. Can you check with the vendor?\n> Tom",
    ),
    # INC-02 sso-gateway ------------------------------------------------------
    ("INC-02", 0): (
        "Entire team locked out",
        "This is urgent. As of about 20 minutes ago nobody on my team can get in. You click sign in, it bounces you over to our company login page, you log in there fine, and then it throws you right back to your sign-in page again. Over and over. 60 people can't work.\n\nWe changed nothing on our side.\n\nGreg Tannen\nIT Administrator, Globex",
    ),
    ("INC-02", 1): (
        "SSO login loop for enterprise accounts",
        "Hello,\n\nSince roughly 07:15 UTC our single sign-on login is looping: users authenticate with our IdP successfully and are redirected back to your login page instead of the app. Reproducible for every user in our org. Password login for our one non-SSO admin account still works.\n\nRegards,\nMei Lin\nEngineering Manager, Initech",
    ),
    # INC-03 payments-gateway -------------------------------------------------
    ("INC-03", 0): (
        "Customer says they were charged twice",
        "Hi,\n\nOne of our customers just called very upset saying the same amount was taken from their card two times this morning for one order. I checked and I can see two entries on our side as well. Is this something on your end? I'm worried other customers may be affected and we haven't heard yet.\n\nThank you,\nArt Vandelay\nVandelay Industries",
    ),
    # INC-04 mobile-bff -------------------------------------------------------
    ("INC-04", 0): (
        "app not updating",
        "the app on my iphone isn't showing anything new. i pull down to refresh and it just snaps back and nothing changes. been like this for an hour. i'm out on site so i can't use a laptop\n\n-jake, umbrella",
    ),
    ("INC-04", 1): (
        "Android app sync failures — multiple users",
        "Hi team,\n\nWe're getting a steady stream of internal tickets from Android users saying the mobile app won't sync: new items don't appear and pull-to-refresh does nothing. iOS users are reporting the same. The web app is fine. Started around 12:30 UTC.\n\nHappy to collect device logs if useful.\n\nNate Kwan\nSupport Lead, Hooli",
    ),
    # INC-05 file-storage -----------------------------------------------------
    ("INC-05", 0): (
        "Can't get our footage in",
        "For the last hour every time I try to add one of our video files it goes all the way to the end of the progress bar and then just fails with a generic 'something went wrong'. Small stuff like thumbnails goes in fine. The big files are the whole point for us.\n\nTony\nStark Media",
    ),
    ("INC-05", 1): (
        "attachments failing",
        "Hello,\n\nI'm trying to attach signed contracts to our matters and they keep failing at the very end. Tried three different files, same thing each time. Smaller PDFs seem OK. Is there an outage?\n\nBest,\nHarriet Lowe\nParalegal, Wayne & Associates",
    ),
    ("INC-05", 2): (
        "Uploads >50MB failing: 500 on /upload/complete",
        "Hi,\n\nLarge uploads are failing consistently since ~15:45 UTC. In the network tab the part uploads all return 200 but the final POST /upload/complete returns a 500 with body {\"error\":\"MultipartCompletionError\"}. Files under ~50MB succeed. Reproduced from two accounts.\n\nMiles Dyson\nCyberdyne",
    ),
    # INC-06 reports-api ------------------------------------------------------
    ("INC-06", 0): (
        "Saved reports won't load",
        "Hi,\n\nOur saved reports have been spinning for a while and then showing an error since about 8am. The smaller ones seem to load, it's the bigger ones with a lot of history that fail. Was working fine yesterday.\n\nThanks for taking a look,\nRichard Hendricks\nPied Piper",
    ),
    # INC-07 search-indexer ---------------------------------------------------
    ("INC-07", 0): (
        "can't find anything from today",
        "Hey! Weird one. Anything we added today just doesn't come up when I look for it. Older stuff comes up fine. If I click through the folders I can see the new things are there, they just don't show up when I type in the box at the top.\n\nPam\nDunder Mifflin",
    ),
    # INC-08 auth-service -----------------------------------------------------
    ("INC-08", 0): (
        "Locked out before a client call",
        "Hi, I've got a call in 15 minutes and I can't get in. I put in my password, then it asks me for the six digit number from my phone, I type it in and it says it's wrong. I've tried five fresh numbers. My phone's time is right. Please help.\n\nDeckard\nSoylent",
    ),
    ("INC-08", 1): (
        "2FA codes rejected for all users",
        "Hello,\n\nSince roughly 13:40 UTC our users cannot complete two-factor login: valid authenticator codes are rejected as incorrect. Affects every user we've tested including brand new enrollments. SSO users are unaffected since they bypass your 2FA.\n\nEldon Tyrell\nSecurity Administrator, Tyrell Corp",
    ),
    # INC-09 invoice-worker (ungrounded) -------------------------------------
    ("INC-09", 0): (
        "September invoice not received",
        "Hello,\n\nWe normally receive our monthly invoice PDF by email on the 1st. It's the 12th and nothing has arrived, and there's nothing in spam. Our account page shows the amount due but there's no document to download. We need the PDF for our AP process.\n\nThanks,\nCave Johnson's office\nAperture Science, Accounts Payable",
    ),
    # INC-10 notifications (ungrounded) --------------------------------------
    ("INC-10", 0): (
        "Not hearing about anything anymore",
        "Hi,\n\nSince yesterday afternoon nobody on my team gets told when someone leaves them a comment or tags them. We used to get an email and a little popup on the phone. Now nothing. People are missing things. Settings all look the same as before.\n\nWilly\nWonka & Co",
    ),
    ("INC-10", 1): (
        "no alerts",
        "haven't gotten any alerts on my phone since yesterday, is that on your end?",
    ),
    # INC-11 exports-renderer (ungrounded) -----------------------------------
    ("INC-11", 0): (
        "CSV export rows broken on multi-line descriptions",
        "Hi,\n\nSince yesterday afternoon our CSV exports are corrupted whenever a record's description contains a line break. The row gets split, e.g.:\n\n  1042,\"Widget A\",\"First line\n  second line\",12.00\n\nturns into two rows on import. Exports from Wednesday and earlier are fine. Scheduling and download both work, it's the file contents.\n\nBill Weasley\nData Engineering, Gringotts",
    ),
    # INC-12 session-store (ungrounded) --------------------------------------
    ("INC-12", 0): (
        "keeps kicking me out",
        "Every couple of hours I get thrown back to the sign in screen and have to log in all over again. Never used to do this. Very annoying when I'm in the middle of something.\n\nWalter\nMassive Dynamic",
    ),
    ("INC-12", 1): (
        "Users being signed out repeatedly",
        "Hi,\n\nSeveral of our users have reported over the last day that they're being signed out and having to log back in multiple times per day, even while actively using the product. No pattern by browser or location that I can see. Login itself works fine once they re-enter their details.\n\nThanks,\nJune Harper\nIT, Veridian Dynamics",
    ),
    # INC-13 dashboard-api (ungrounded) --------------------------------------
    ("INC-13", 0): (
        "Numbers wrong",
        "The figures on the first screen when I log in don't match what I see when I click into the details. First screen is behind by a lot. Which one is right?\n\nRobert Angier\nPrestige",
    ),
    # INC-14 billing-api (ungrounded) ----------------------------------------
    ("INC-14", 0): (
        "Seat count wrong after upgrade",
        "Hello,\n\nWe upgraded our plan this morning to get 25 seats. The billing page still says we have 10, and when I try to add an 11th person it tells me we're at our limit. The receipt for the upgrade did come through.\n\nMichael Bluth\nBluth Company",
    ),
    # INC-15 web-bff (ungrounded) --------------------------------------------
    ("INC-15", 0): (
        "Home screen looks off",
        "Hi,\n\nSince yesterday evening the boxes on the main page after I log in are all in a different order than they were, and one of them is stretched across the whole width. It's the browser version, I haven't checked the phone. Nothing seems broken exactly, it just looks wrong and my team is confused.\n\nJoan Holloway\nSterling Cooper",
    ),
}
