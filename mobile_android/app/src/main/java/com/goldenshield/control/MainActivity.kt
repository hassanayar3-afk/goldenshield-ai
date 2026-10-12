package com.goldenshield.control

import android.annotation.SuppressLint
import android.content.Context
import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var urlField: EditText
    private lateinit var webView: WebView
    private lateinit var bar: LinearLayout

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        urlField = findViewById(R.id.server_url)
        webView = findViewById(R.id.webview)
        bar = findViewById(R.id.url_bar)
        val openBtn: Button = findViewById(R.id.btn_open)

        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val saved = prefs.getString(KEY_URL, DEFAULT_URL) ?: DEFAULT_URL
        urlField.setText(saved)

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = WebViewClient()

        openBtn.setOnClickListener { openPanel() }

        if (intent.getBooleanExtra(EXTRA_AUTO_OPEN, true)) {
            openPanel()
        }
    }

    private fun openPanel() {
        val raw = urlField.text?.toString()?.trim().orEmpty()
        if (raw.isEmpty()) {
            Toast.makeText(this, R.string.hint_url, Toast.LENGTH_SHORT).show()
            return
        }
        val base = normalizeBase(raw)
        getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_URL, base)
            .apply()
        bar.visibility = View.GONE
        webView.loadUrl(base)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else if (bar.visibility == View.GONE) {
            bar.visibility = View.VISIBLE
        } else {
            super.onBackPressed()
        }
    }

    companion object {
        private const val PREFS = "gs_control"
        private const val KEY_URL = "server_base_url"
        private const val EXTRA_AUTO_OPEN = "auto_open"
        private const val DEFAULT_URL = "http://127.0.0.1:8790/"

        private fun normalizeBase(raw: String): String {
            var s = raw.trim()
            if (!s.startsWith("http://") && !s.startsWith("https://")) {
                s = "https://$s"
            }
            if (!s.endsWith("/")) s += "/"
            return s
        }
    }
}
