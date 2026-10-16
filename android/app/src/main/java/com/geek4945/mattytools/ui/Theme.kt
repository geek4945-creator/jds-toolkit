package com.geek4945.mattytools.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.geek4945.mattytools.data.ThemeMode

private val Indigo = Color(0xFF4F46E5)

private val Light = lightColorScheme(
    primary = Indigo, onPrimary = Color.White, primaryContainer = Color(0xFFE0E7FF), onPrimaryContainer = Color(0xFF1E1B4B),
    secondary = Color(0xFF0F766E), secondaryContainer = Color(0xFFCCFBF1), onSecondaryContainer = Color(0xFF042F2E),
    tertiary = Color(0xFFDB2777), background = Color(0xFFFBFBFE), surface = Color(0xFFFBFBFE),
    surfaceVariant = Color(0xFFEEF0F8), onSurfaceVariant = Color(0xFF454B5F), outline = Color(0xFF8A90A6),
)
private val Dark = darkColorScheme(
    primary = Color(0xFFA5B4FC), onPrimary = Color(0xFF1E1B4B), primaryContainer = Color(0xFF312E81), onPrimaryContainer = Color(0xFFE0E7FF),
    secondary = Color(0xFF5EEAD4), secondaryContainer = Color(0xFF134E4A), onSecondaryContainer = Color(0xFFCCFBF1),
    tertiary = Color(0xFFF9A8D4), background = Color(0xFF0F1115), surface = Color(0xFF0F1115),
    surfaceVariant = Color(0xFF1C1F27), onSurfaceVariant = Color(0xFFC3C8DA), outline = Color(0xFF7C8298),
)

@Composable
fun MattyTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) { ThemeMode.SYSTEM -> isSystemInDarkTheme(); ThemeMode.LIGHT -> false; ThemeMode.DARK -> true }
    MaterialTheme(colorScheme = if (dark) Dark else Light, content = content)
}
