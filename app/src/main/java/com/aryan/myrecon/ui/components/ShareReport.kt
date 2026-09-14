package com.aryan.myrecon.ui.components

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.IosShare
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.LocalHaptics

/**
 * Hand a finished report to whatever app the user wants to send it with.
 *
 * A chooser rather than a hardcoded target: the person who needs to see this is
 * reached over WhatsApp for one user, email for another, and a notes app for
 * someone keeping a record before they report it.
 *
 * Nothing is uploaded. The text is passed to another app on the same phone, at
 * the moment the user picks one — which is why the button says share rather
 * than send.
 */
fun shareReport(context: Context, subject: String, body: String) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_SUBJECT, subject)
        putExtra(Intent.EXTRA_TEXT, body)
    }
    // A chooser every time, even when a default exists. Sharing a report about
    // a person is not something to fire into whichever app happened to be
    // remembered from last time.
    val chooser = Intent.createChooser(intent, "Share this report").apply {
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    runCatching { context.startActivity(chooser) }
}

@Composable
fun ShareButton(
    subject: String,
    body: String,
    label: String = "Share this report",
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val haptics = LocalHaptics.current
    OutlinedButton(
        onClick = {
            haptics.tap()
            shareReport(context, subject, body)
        },
        shape = RoundedCornerShape(11.dp),
        modifier = modifier,
    ) {
        Icon(Icons.Filled.IosShare, contentDescription = null, modifier = Modifier.size(17.dp))
        Spacer(Modifier.width(8.dp))
        Text(label)
    }
}
