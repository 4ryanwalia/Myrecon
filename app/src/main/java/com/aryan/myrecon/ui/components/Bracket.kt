package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.Mono

/**
 * Corner brackets instead of a full border.
 *
 * A closed rounded rectangle reads as a card — a web idiom. Four corner marks
 * read as a registration frame: a viewfinder, a crop guide, a targeting
 * reticle. It is the cheapest way to make a panel look like instrumentation
 * rather than content, and it is the same language already used by the QR
 * scanner's reticle, so the app agrees with itself.
 *
 * Deliberately not glass: no translucency, no blur, no gradient fill. The
 * surface is opaque and nearly black, and the structure comes from the marks.
 */
fun Modifier.bracketFrame(
    colour: Color,
    armLength: Dp = 13.dp,
    stroke: Dp = 1.5.dp,
    inset: Dp = 0.dp,
): Modifier = drawBehind {
    val arm = armLength.toPx()
    val w = stroke.toPx()
    val pad = inset.toPx()
    val l = pad
    val t = pad
    val r = size.width - pad
    val b = size.height - pad

    fun corner(x: Float, y: Float, dx: Float, dy: Float) {
        drawLine(colour, Offset(x, y), Offset(x + dx, y), w, StrokeCap.Square)
        drawLine(colour, Offset(x, y), Offset(x, y + dy), w, StrokeCap.Square)
    }
    corner(l, t, arm, arm)
    corner(r, t, -arm, arm)
    corner(l, b, arm, -arm)
    corner(r, b, -arm, -arm)
}

/**
 * Panel with a label cut into its top rule.
 *
 * The label sits on the frame line rather than inside the box, the way a
 * schematic annotates a region. It also saves the vertical space a separate
 * heading would cost, which matters on a data-dense screen.
 */
@Composable
fun InstrumentPanel(
    label: String,
    modifier: Modifier = Modifier,
    accent: Color? = null,
    trailing: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val t = LocalReconTokens.current
    val edge = accent ?: t.border

    Column(modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().padding(bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                label.uppercase(),
                fontFamily = Mono,
                style = MaterialTheme.typography.labelSmall,
                color = accent ?: t.textMute,
            )
            Spacer(Modifier.width(8.dp))
            // Rule running to the trailing value, so the eye is carried across.
            Box(
                Modifier
                    .weight(1f)
                    .height(1.dp)
                    .background(edge.copy(alpha = 0.5f)),
            )
            if (trailing != null) {
                Spacer(Modifier.width(8.dp))
                Text(
                    trailing,
                    fontFamily = Mono,
                    style = MaterialTheme.typography.labelSmall,
                    color = t.textMute,
                )
            }
        }
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(3.dp))
                .background(MaterialTheme.colorScheme.surface)
                .bracketFrame(edge)
                .padding(14.dp),
            content = content,
        )
    }
}

/**
 * Monospace key/value line, aligned on a leader of dots.
 *
 * The leader is what makes a column of readings scan as a table without
 * drawing one, and it is a convention borrowed from technical listings rather
 * than from web layout.
 */
@Composable
fun ReadoutRow(key: String, value: String, valueColour: Color? = null) {
    val t = LocalReconTokens.current
    Row(
        Modifier.fillMaxWidth().padding(vertical = 5.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(
            key.uppercase(),
            fontFamily = Mono,
            style = MaterialTheme.typography.labelSmall,
            color = t.textMute,
        )
        Box(
            Modifier
                .weight(1f)
                .padding(horizontal = 6.dp, vertical = 4.dp)
                .height(1.dp)
                .background(t.border.copy(alpha = 0.55f)),
        )
        Text(
            value.ifBlank { "—" },
            fontFamily = Mono,
            style = MaterialTheme.typography.bodySmall,
            color = valueColour ?: MaterialTheme.colorScheme.onSurface,
        )
    }
}

/** Terminal-style status line: `> checking github…` */
@Composable
fun TerminalLine(
    text: String,
    prefix: String = ">",
    colour: Color? = null,
) {
    val t = LocalReconTokens.current
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text(
            prefix,
            fontFamily = Mono,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.width(7.dp))
        Text(
            text,
            fontFamily = Mono,
            style = MaterialTheme.typography.bodySmall,
            color = colour ?: t.textDim,
            maxLines = 1,
        )
    }
}
