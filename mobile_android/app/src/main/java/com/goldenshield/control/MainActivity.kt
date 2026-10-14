package com.goldenshield.control

import android.annotation.SuppressLint
import android.content.Context
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val prefs by lazy { getSharedPreferences("gs_panel", Context.MODE_PRIVATE) }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webview)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = WebViewClient()
        webView.loadUrl("about:blank")

        Executors.newSingleThreadExecutor().execute {
            val panelUrl = resolvePanelUrl()
            runOnUiThread { webView.loadUrl(panelUrl) }
        }
    }

    private fun resolvePanelUrl(): String {
        val candidates = mutableListOf<String>()
        prefs.getString("last_good_base", null)?.let { candidates.add(it) }
        val built = BuildConfig.PANEL_URL.trim().trimEnd('/')
        if (built.startsWith("http")) {
            candidates.add(built)
        }
        candidates.addAll(readAssetServers())
        val seen = linkedSetOf<String>()
        for (raw in candidates) {
            val base = raw.trim().trimEnd('/')
            if (!base.startsWith("http") || !seen.add(base)) {
                continue
            }
            if (!healthOk(base)) {
                continue
            }
            val pair = fetchPairCode(base) ?: continue
            prefs.edit().putString("last_good_base", base).apply()
            val q = URLEncoder.encode(pair, Charsets.UTF_8.name())
            return "$base/?pair_code=$q"
        }
        return if (built.startsWith("http")) built + "/" else "about:blank"
    }

    private fun readAssetServers(): List<String> {
        return try {
            assets.open("default_servers.txt").use { ins ->
                BufferedReader(InputStreamReader(ins)).readLines()
                    .map { it.trim() }
                    .filter { it.startsWith("http") && !it.startsWith("#") }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun healthOk(base: String): Boolean {
        return try {
            val conn = openGet("$base/api/health", 9000)
            conn.responseCode in 200..299
        } catch (_: Exception) {
            false
        }
    }

    private fun fetchPairCode(base: String): String? {
        return try {
            val conn = openGet("$base/api/bootstrap", 12000)
            if (conn.responseCode !in 200..299) {
                return null
            }
            val body = conn.inputStream.bufferedReader().readText()
            val json = JSONObject(body)
            val code = json.optString("pair_code").ifBlank {
                json.optString("mobile_pair_code")
            }
            code.ifBlank { null }
        } catch (_: Exception) {
            null
        }
    }

    private fun openGet(url: String, timeoutMs: Int): HttpURLConnection {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = timeoutMs
        conn.readTimeout = timeoutMs
        conn.instanceFollowRedirects = true
        conn.connect()
        return conn
    }

    override fun onResume() {
        super.onResume()
        Executors.newSingleThreadExecutor().execute {
            val base = prefs.getString("last_good_base", null)?.trim()?.trimEnd('/')
            if (base.isNullOrBlank() || !base.startsWith("http")) {
                return@execute
            }
            if (!healthOk(base)) {
                val panelUrl = resolvePanelUrl()
                runOnUiThread { webView.loadUrl(panelUrl) }
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
