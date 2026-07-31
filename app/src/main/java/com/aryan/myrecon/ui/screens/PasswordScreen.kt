package com.aryan.myrecon.ui.screens

import android.app.Activity
import android.view.WindowManager
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aryan.myrecon.data.PwnedPasswords
import com.aryan.myrecon.ui.components.DataList
import com.aryan.myrecon.ui.components.SectionLabel
import com.aryan.myrecon.ui.components.StatePanel
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoScore
import com.aryan.myrecon.ui.theme.MonoStyle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface PwState {
    data object Idle : PwState
    data object Checking : PwState
    data class Done(val result: PwnedPasswords.Result) : PwState
    data class Failed(val message: String) : PwState
}

class PasswordViewModel : ViewModel() {
    private val _state = MutableStateFlow<PwState>(PwState.Idle)
    val state = _state.asStateFlow()

    fun check(password: String) {
        if (password.isEmpty()) return
        viewModelScope.launch {
            _state.value = PwState.Checking
            _state.value = try {
                PwState.Done(PwnedPasswords.check(password))
            } catch (e: Throwable) {
                PwState.Failed(e.message ?: "The check could not be completed.")
            }
        }
    }

    fun reset() { _state.value = PwState.Idle }
}

@Composable
fun PasswordScreen(vm: PasswordViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val t = LocalReconTokens.current
    val keyboard = LocalSoftwareKeyboardController.current

    // Deliberately plain local state, never a ViewModel field: a ViewModel
    // survives configuration changes and would keep the secret in memory across
    // rotation. This dies with the composable.
    var password by remember { mutableStateOf("") }
    var revealed by remember { mutableStateOf(false) }

    // Block screenshots and the recents-screen thumbnail while this tab is
    // open. Without it a revealed password is captured into the task snapshot
    // the moment the user switches apps, and that snapshot outlives the screen.
    val view = LocalView.current
    DisposableEffect(Unit) {
        val window = (view.context as? Activity)?.window
        window?.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        onDispose { window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(bottom = 40.dp),
    ) {
        Spacer(Modifier.height(16.dp))
        Text("Password exposure", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(6.dp))
        Text(
            "Checks a password against hundreds of millions of credentials recovered from " +
                "breach dumps. It is hashed on this device and only the first five characters " +
                "of the hash are sent — the password itself never leaves your phone.",
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )

        Spacer(Modifier.height(16.dp))

        OutlinedTextField(
            value = password,
            onValueChange = { password = it; if (state !is PwState.Idle) vm.reset() },
            placeholder = { Text("Type or paste a password", style = MonoStyle, color = t.textMute) },
            singleLine = true,
            textStyle = MonoStyle.copy(color = MaterialTheme.colorScheme.onSurface),
            visualTransformation = if (revealed) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.None,
                autoCorrectEnabled = false,
                imeAction = ImeAction.Go,
                // Tells the keyboard this is a password field, which stops it
                // adding the text to its personal dictionary or predictions.
                // Otherwise the secret can end up suggested in other apps.
                keyboardType = KeyboardType.Password,
            ),
            keyboardActions = KeyboardActions(onGo = { keyboard?.hide(); vm.check(password) }),
            trailingIcon = {
                IconButton(onClick = { revealed = !revealed }) {
                    Icon(
                        if (revealed) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                        contentDescription = if (revealed) "Hide password" else "Show password",
                        tint = t.textMute,
                    )
                }
            },
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth(),
        )

        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { keyboard?.hide(); vm.check(password) },
            enabled = password.isNotEmpty() && state !is PwState.Checking,
            shape = RoundedCornerShape(11.dp),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Check privately") }

        Spacer(Modifier.height(18.dp))

        when (val s = state) {
            is PwState.Idle -> StatePanel(
                "Nothing sent yet",
                "Your password is hashed locally with SHA-1. Only a five-character prefix of " +
                    "that hash is sent, and thousands of unrelated passwords share it.",
            )

            is PwState.Checking -> StatePanel("Checking…", "Hashing locally and comparing against the corpus.")

            is PwState.Failed -> StatePanel("Check failed", s.message, tint = t.danger)

            is PwState.Done -> PasswordResult(s.result)
        }
    }
}

@Composable
private fun PasswordResult(r: PwnedPasswords.Result) {
    val t = LocalReconTokens.current
    val tint = if (r.breached) t.danger else t.ok

    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(tint.copy(alpha = 0.10f))
            .border(1.dp, tint.copy(alpha = 0.4f), RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (r.breached) "Found in breach data" else "Not found in breach data",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            Text(
                if (r.breached) "%,d".format(r.breachCount) else "no match",
                style = MonoScore, color = tint,
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(
            if (r.breached) {
                "Stop using this password anywhere it appears. Attackers load exactly these " +
                    "lists into credential-stuffing tools, so how strong it looks no longer matters."
            } else {
                "This password is not in the corpus. That means it has not appeared in a known " +
                    "dump — it does not by itself mean the password is strong."
            },
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
        )
    }

    SectionLabel("Brute-force resistance")
    DataList(
        listOf(
            "Strength" to "${r.strength.label} — ${r.strength.bits} bits",
            "Length" to "${r.strength.length} characters",
            "Character pool" to "${r.strength.poolSize} per position",
            "Offline crack time" to r.strength.crackTime,
        )
    )
    Spacer(Modifier.height(10.dp))
    Text(
        "Estimated against roughly 100 billion guesses per second — a mid-range GPU rig " +
            "attacking a fast hash. A site using a slow hash such as bcrypt would take far longer.",
        style = MaterialTheme.typography.bodySmall,
        color = t.textMute,
    )
}
