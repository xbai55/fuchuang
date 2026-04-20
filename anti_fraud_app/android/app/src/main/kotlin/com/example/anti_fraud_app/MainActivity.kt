package com.example.anti_fraud_app

import android.content.Intent
import android.net.Uri
import android.speech.tts.TextToSpeech
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.Locale

class MainActivity : FlutterActivity() {
    private val emergencyChannel = "tianshu_mingyu/emergency_actions"
    private var textToSpeech: TextToSpeech? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, emergencyChannel)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "dial" -> {
                        val number = call.argument<String>("number").orEmpty()
                        result.success(openDialer(number))
                    }

                    "speak" -> {
                        val text = call.argument<String>("text").orEmpty()
                        val language = call.argument<String>("language").orEmpty()
                        result.success(speakWarning(text, language))
                    }

                    else -> result.notImplemented()
                }
            }
    }

    private fun openDialer(number: String): Boolean {
        val sanitized = number.replace(Regex("[^\\d+]"), "")
        if (sanitized.isBlank()) {
            return false
        }

        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$sanitized"))
        if (intent.resolveActivity(packageManager) == null) {
            return false
        }

        startActivity(intent)
        return true
    }

    private fun speakWarning(text: String, language: String): Boolean {
        if (text.isBlank()) {
            return false
        }

        val locale = if (language.lowercase(Locale.ROOT).startsWith("en")) {
            Locale.US
        } else {
            Locale.SIMPLIFIED_CHINESE
        }

        val currentSpeaker = textToSpeech
        if (currentSpeaker == null) {
            textToSpeech = TextToSpeech(this) { status ->
                if (status == TextToSpeech.SUCCESS) {
                    textToSpeech?.language = locale
                    textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "risk-warning")
                }
            }
            return true
        }

        currentSpeaker.language = locale
        currentSpeaker.speak(text, TextToSpeech.QUEUE_FLUSH, null, "risk-warning")
        return true
    }

    override fun onDestroy() {
        textToSpeech?.shutdown()
        textToSpeech = null
        super.onDestroy()
    }
}
