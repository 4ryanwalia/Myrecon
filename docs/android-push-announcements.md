# MyRecon push announcements

The Android app subscribes to the public Firebase Cloud Messaging topic
`myrecon_announcements` (release builds) or `myrecon_announcements_debug`
(debug, phoneDebug and other debuggable builds). This supports sending a new
title and message at any time without changing the app again. No login is required.

Foreground messages are displayed by `AnnouncementService`. Background messages
use FCM's notification payload and the same `app_announcements` channel. Tapping
opens MyRecon. Users can control this channel through **Privacy → Notification
settings** without disabling breach watches. Android 13+ users see an explanatory
permission prompt after onboarding; declining does not prevent using the app.

## Private sending workflow

Tell the assistant the exact title and body and ask it to send. The assistant can
run `tools/send_app_notification.py` from this workspace. Sending credentials stay
on the trusted operator machine; there is no public broadcast endpoint or sender
key inside the app.

Preview (no credentials or network required):

```powershell
python tools/send_app_notification.py --title "Your title" --body "Your message"
```

Use a service account in Firebase project `myrecon-bugsnaps` with permission
`cloudmessaging.messages.create` (Firebase Cloud Messaging API Admin role), with
the Firebase Cloud Messaging API enabled. Configure either:

- `GOOGLE_APPLICATION_CREDENTIALS`: absolute path to its private JSON file outside
  the repository, or
- `FIREBASE_SERVICE_ACCOUNT`: raw JSON or base64 JSON, matching the backend's format.

The sender uses `requests` and `PyJWT[crypto]` already listed in backend requirements.
Do not copy credentials into source, docs, chat, APKs, or command arguments.

Validate permissions and payload with Firebase, without delivery:

```powershell
python tools/send_app_notification.py --title "Your title" --body "Your message" --debug --validate
```

Test on debug installations:

```powershell
python tools/send_app_notification.py --title "Test" --body "Push delivery test" --debug --send
```

Broadcast the user's authorized message to release installations:

```powershell
python tools/send_app_notification.py --title "Your title" --body "Your message" --send
```

`--token` targets a single installation instead of a topic. `--validate` and
`--send` are mutually exclusive. Do not repeat a timed-out send automatically:
Firebase may have accepted it before the connection failed, and retrying can send
duplicates. FCM's returned message ID confirms acceptance, not delivery or reads.

## Release and verification

Existing installed app versions cannot receive these broadcasts. Build, sign and
publish an update containing the new dependency, manifest service and messaging
classes. Recipients must update, launch it at least once to subscribe, and enable
notifications. Devices need working Google Play services; force stop, offline
devices and battery restrictions can delay or prevent delivery. Messages expire
after 24 hours. Topic delivery is best effort and should contain public news only.

Before release, test on Android 13+ and Android 12: permission allow/deny, app in
foreground/background, tapping a message, channel disabled, and debug topic
isolation. Validate service-account permissions separately. No broadcast is sent
by the build or unit tests.

The Android project is deliberately ignored by Git in this workspace. Preserve
its local changes/backups; pushing the website does not release this feature.

References: [Android reception](https://firebase.google.com/docs/cloud-messaging/android/receive-messages),
[HTTP v1 sending](https://firebase.google.com/docs/cloud-messaging/send/v1-api).
