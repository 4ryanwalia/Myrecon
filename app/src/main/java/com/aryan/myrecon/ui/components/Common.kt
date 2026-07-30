package com.aryan.myrecon.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.aryan.myrecon.ui.theme.LocalReconTokens
import com.aryan.myrecon.ui.theme.MonoStyle

/** Uppercase eyebrow above a block of results. Mirrors `.section-label` on web. */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = LocalReconTokens.current.textMute,
        modifier = modifier.padding(top = 18.dp, bottom = 8.dp),
    )
}

/** Bordered container used for every result block. */
@Composable
fun ReconCard(
    modifier: Modifier = Modifier,
    stripe: Color? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val t = LocalReconTokens.current
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(t.bgSoft)
            .border(1.dp, t.border, RoundedCornerShape(12.dp)),
    ) {
        // A severity stripe reads faster than a number — state encoded in form
        // as well as value, so what needs attention is visible at a glance.
        if (stripe != null) {
            Box(
                Modifier
                    .width(3.dp)
                    .fillMaxHeight()
                    .background(stripe),
            )
        }
        Column(Modifier.padding(14.dp), content = content)
    }
}

/** Small monospace tag. `strong` marks corroborated evidence. */
@Composable
fun Chip(text: String, strong: Boolean = false, danger: Boolean = false) {
    val t = LocalReconTokens.current
    val fg = when {
        danger -> t.danger
        strong -> t.ok
        else -> t.textMute
    }
    Text(
        text,
        style = MonoStyle.copy(fontSize = androidx.compose.ui.unit.TextUnit(10.5f, androidx.compose.ui.unit.TextUnitType.Sp)),
        color = fg,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier
            .clip(RoundedCornerShape(5.dp))
            .border(1.dp, if (fg == t.textMute) t.border else fg.copy(alpha = 0.4f), RoundedCornerShape(5.dp))
            .padding(horizontal = 7.dp, vertical = 3.dp),
    )
}

/** Key/value row. The value is monospace: it is measured data. */
@Composable
fun DataRow(key: String, value: String) {
    val t = LocalReconTokens.current
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 7.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(
            key,
            style = MaterialTheme.typography.bodySmall,
            color = t.textMute,
            modifier = Modifier.weight(0.42f),
        )
        Text(
            value.ifBlank { "—" },
            style = MonoStyle,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(0.58f),
        )
    }
}

@Composable
fun DataList(rows: List<Pair<String, String>>) {
    val t = LocalReconTokens.current
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, t.border, RoundedCornerShape(12.dp))
            .padding(horizontal = 14.dp, vertical = 4.dp),
    ) {
        rows.forEachIndexed { i, (k, v) ->
            if (i > 0) HorizontalDivider(color = t.border.copy(alpha = 0.5f))
            DataRow(k, v)
        }
    }
}

/** Empty / error / loading placeholder. */
@Composable
fun StatePanel(title: String, body: String, tint: Color? = null) {
    val t = LocalReconTokens.current
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, tint ?: t.border, RoundedCornerShape(14.dp))
            .padding(22.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium, color = tint ?: MaterialTheme.colorScheme.onSurface)
        Spacer(Modifier.height(6.dp))
        Text(
            body,
            style = MaterialTheme.typography.bodySmall,
            color = t.textDim,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

/** Wrapping row of chips. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChipRow(items: List<String>, strongPredicate: (String) -> Boolean = { false }, dangerPredicate: (String) -> Boolean = { false }) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalArrangement = Arrangement.spacedBy(5.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        items.forEach { Chip(it, strong = strongPredicate(it), danger = dangerPredicate(it)) }
    }
}
