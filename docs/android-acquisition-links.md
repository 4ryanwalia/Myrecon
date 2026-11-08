# MyRecon Android campaign links

Use the default Play listing and one link per channel. The referrer is
URL-encoded and contains only campaign identifiers, not personal data. These
links have not been posted to any channel.

| Channel | Play link |
| --- | --- |
| YouTube | https://play.google.com/store/apps/details?id=com.Myrecon.osint&referrer=utm_source%3Dyoutube%26utm_medium%3Dvideo%26utm_campaign%3Dmyrecon_youtube |
| Social posts | https://play.google.com/store/apps/details?id=com.Myrecon.osint&referrer=utm_source%3Dsocial%26utm_medium%3Dsocial%26utm_campaign%3Dmyrecon_social |
| Partner | https://play.google.com/store/apps/details?id=com.Myrecon.osint&referrer=utm_source%3Dpartner%26utm_medium%3Dreferral%26utm_campaign%3Dmyrecon_partner |

Use a distinct, non-personal `utm_source` for each social platform or partner
when a more detailed breakdown is useful. Build the referrer by URL-encoding
the full `utm_source=...&utm_medium=...&utm_campaign=...` string; keep any
invite code separate. Website banners already use topic-specific campaigns,
and breach and case-file links use their own sources of traffic.

In Play Console, review Grow users > Store performance > Conversion analysis,
filtering traffic source to ads and referrals, then inspect UTM source and
campaign. Listing clicks represent intent, so review completed acquisitions
separately in Grow overview or Statistics. Reporting can group low-volume or
unattributed traffic, so these links do not guarantee per-channel install
counts. See [Google's acquisition reporting guide](https://support.google.com/googleplay/android-developer/answer/9859173).

The `breach-alerts` custom listing is not currently present in Play Console;
the links above intentionally use the default listing. Create and validate a
custom listing before introducing a `listing` parameter.
