package com.goldenshield.control

import android.annotation.SuppressLint
import android.content.Context
import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import java.net.HttpURLConnection
import java.net.URL
import java.util.regex.Pattern

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
        val discoverBtn: Button = findViewById(R.id.btn_discover)
        val testBtn: Button = findViewById(R.id.btn_test)

        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val saved = prefs.getString(KEY_URL, "") ?: ""
        if (saved.isNotBlank()) {
            urlField.setText(saved.trim())
        }

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                if (request.isForMainFrame) {
                    bar.visibility = View.VISIBLE
                    Toast.makeText(this@MainActivity, R.string.web_error, Toast.LENGTH_LONG).show()
                }
            }
        }

        openBtn.setOnClickListener { openPanel() }
        discoverBtn.setOnClickListener { discoverTunnel() }
        testBtn.setOnClickListener { testConnection(false) }
    }

    private fun testConnection(thenOpen: Boolean) {
        val raw = urlField.text?.toString()?.trim().orEmpty()
        if (raw.isEmpty()) {
            Toast.makeText(this, R.string.hint_url, Toast.LENGTH_SHORT).show()
            return
        }
        if (isLocalhostOnly(raw) && !isTermuxLikely()) {
            Toast.makeText(this, R.string.err_localhost, Toast.LENGTH_LONG).show()
            return
        }
        val base = normalizeBase(raw)
        Thread {
            val ok = try {
                val body = httpGet("${base}api/health")
                body.contains("\"ok\"") && body.contains("true")
            } catch (_: Exception) {
                false
            }
            runOnUiThread {
                if (ok) {
                    saveUrl(base)
                    Toast.makeText(this, R.string.test_ok, Toast.LENGTH_SHORT).show()
                    if (thenOpen) openPanel(skipLocalCheck = true)
                } else {
                    Toast.makeText(this, R.string.test_fail, Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun isTermuxLikely(): Boolean {
        return try {
            Class.forName("com.termux.app.TermuxActivity")
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun isLocalhostOnly(raw: String): Boolean {
        val s = raw.lowercase()
        return s.contains("127.0.0.1") || s.contains("localhost")
    }

    private fun discoverTunnel() {
        val seed = urlField.text?.toString()?.trim().orEmpty()
        if (seed.isEmpty()) {
            Toast.makeText(this, R.string.hint_url, Toast.LENGTH_SHORT).show()
            return
        }
        val seedBase = normalizeBase(seed)
        Thread {
            val picked = resolvePublicBase(seedBase)
            runOnUiThread {
                urlField.setText(picked)
                Toast.makeText(this, R.string.discover_ok, Toast.LENGTH_SHORT).show()
                testConnection(thenOpen = true)
            }
        }.start()
    }

    private fun resolvePublicBase(seedBase: String): String {
        val hints = mutableListOf<String>()
        try {
            val cfg = httpGet("${seedBase}api/mobile/config")
            extractJsonString(cfg, "tunnel_url")?.let { hints.add(it) }
        } catch (_: Exception) {
        }
        try {
            val boot = httpGet("${seedBase}api/bootstrap")
            extractJsonString(boot, "api_base_hint")?.let { hints.add(it) }
            extractJsonString(boot, "tunnel_url")?.let { hints.add(it) }
        } catch (_: Exception) {
        }
        try {
            val live = httpGet("${seedBase}download/live-base").trim()
            if (live.startsWith("http")) hints.add(live)
        } catch (_: Exception) {
        }
        hints.add(seedBase)
        return hints.firstOrNull { it.startsWith("https://") }?.let { normalizeBase(it) }
            ?: normalizeBase(hints.first())
    }

    private fun httpGet(url: String): String {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15000
        conn.readTimeout = 15000
        conn.requestMethod = "GET"
        conn.inputStream.bufferedReader().use { return it.readText() }
    }

    private fun extractJsonString(json: String, key: String): String? {
        val p = Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*\"([^\"]*)\"")
        val m = p.matcher(json)
        return if (m.find()) m.group(1)?.takeIf { it.isNotBlank() } else null
    }

    private fun saveUrl(base: String) {
        getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_URL, base)
            .apply()
    }

    private fun openPanel(skipLocalCheck: Boolean = false) {
        val raw = urlField.text?.toString()?.trim().orEmpty()
        if (raw.isEmpty()) {
            Toast.makeText(this, R.string.hint_url, Toast.LENGTH_SHORT).show()
            return
        }
        if (!skipLocalCheck && isLocalhostOnly(raw) && !isTermuxLikely()) {
            Toast.makeText(this, R.string.err_localhost, Toast.LENGTH_LONG).show()
            return
        }
        val base = normalizeBase(raw)
        saveUrl(base)
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
