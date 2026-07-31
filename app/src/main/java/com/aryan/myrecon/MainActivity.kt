package com.aryan.myrecon

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.LocalHaptics
import com.aryan.myrecon.ui.components.AdBanner
import com.aryan.myrecon.ui.rememberHaptics
import com.aryan.myrecon.ui.screens.ImageScreen
import com.aryan.myrecon.ui.screens.LookupScreen
import com.aryan.myrecon.ui.screens.PasswordScreen
import com.aryan.myrecon.ui.screens.ScanScreen
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MyReconTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // One Haptics instance for the whole tree — screens reach for it
            // through LocalHaptics rather than each resolving the Vibrator.
            CompositionLocalProvider(LocalHaptics provides rememberHaptics()) {
                MyReconTheme { MyReconApp() }
            }
        }
    }
}

private enum class Destination(val label: String, val icon: ImageVector) {
    Lookup("Lookup", Icons.Filled.Search),
    Scan("Scan", Icons.Filled.QrCodeScanner),
    Image("Image", Icons.Filled.Image),
    Password("Password", Icons.Filled.Lock),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MyReconApp() {
    var current by rememberSaveable { mutableStateOf(Destination.Lookup) }
    val t = LocalReconTokens.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Image(
                            painter = painterResource(R.drawable.ic_logo),
                            contentDescription = null,
                            modifier = Modifier.size(30.dp),
                        )
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text("MyRecon", style = MaterialTheme.typography.titleLarge)
                            Text(
                                "OSINT · public sources only",
                                style = MaterialTheme.typography.labelSmall,
                                color = t.textMute,
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        bottomBar = {
            Column {
                // Anchored above the nav and outside the scroll container, so
                // it never slides under a finger mid-scroll — the most common
                // source of accidental clicks, which AdMob counts as invalid
                // traffic. Hidden on the password screen: an ad next to a field
                // where someone types a secret is a trust problem, whatever the
                // policy says.
                if (current != Destination.Password) AdBanner()

                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                    val haptics = LocalHaptics.current
                    Destination.entries.forEach { d ->
                        NavigationBarItem(
                            selected = current == d,
                            onClick = { if (current != d) haptics.tap(); current = d },
                            icon = { Icon(d.icon, contentDescription = null) },
                            label = { Text(d.label) },
                        )
                    }
                }
            }
        },
    ) { inner ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(inner),
        ) {
            // Each destination keeps its own ViewModel, so switching tabs does
            // not discard an in-flight scan or a rendered result.
            when (current) {
                Destination.Lookup -> LookupScreen()
                Destination.Scan -> ScanScreen()
                Destination.Image -> ImageScreen()
                Destination.Password -> PasswordScreen()
            }
        }
    }
}
