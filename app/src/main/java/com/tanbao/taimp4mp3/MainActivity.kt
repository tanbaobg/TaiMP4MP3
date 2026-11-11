package com.tanbao.taimp4mp3

import android.Manifest
import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.webkit.*
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import java.io.File
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.regex.Pattern

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var swipeRefreshLayout: SwipeRefreshLayout
    private var pendingDownloadRequest: DownloadManager.Request? = null

    private val requestNotificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            // Notification permission result (Android 13+)
        }

    private val requestStoragePermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (isGranted) {
                pendingDownloadRequest?.let { req ->
                    val manager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                    manager.enqueue(req)
                    pendingDownloadRequest = null
                    Toast.makeText(this, "Đang bắt đầu tải xuống...", Toast.LENGTH_SHORT).show()
                }
            } else {
                Toast.makeText(this, getString(R.string.storage_permission_required), Toast.LENGTH_LONG).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        checkPermissions()

        swipeRefreshLayout = findViewById(R.id.swipeRefreshLayout)
        webView = findViewById(R.id.webView)

        setupWebView()
        setupSwipeRefresh()
        setupBackNavigation()

        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        intent?.let { handleIntent(it) }
    }

    private fun checkPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = true
        settings.mediaPlaybackRequiresUserGesture = false
        settings.cacheMode = WebSettings.LOAD_DEFAULT

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                swipeRefreshLayout.isRefreshing = false
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url?.toString() ?: return false
                if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("file://")) {
                    return false
                }
                return try {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    startActivity(intent)
                    true
                } catch (e: Exception) {
                    false
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            // Optional support for custom full screen or alerts
        }

        // Native Download Listener: Catches all video/audio downloads
        webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            startNativeDownload(url, userAgent, contentDisposition, mimeType)
        }
    }

    private fun startNativeDownload(url: String, userAgent: String?, contentDisposition: String?, mimeType: String?) {
        try {
            var fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
            
            // Try extracting better filename from title parameter if available
            val uri = Uri.parse(url)
            val titleParam = uri.getQueryParameter("title")
            val extParam = uri.getQueryParameter("ext")
            if (!titleParam.isNullOrBlank()) {
                val ext = extParam ?: if (mimeType?.contains("audio") == true) "mp3" else "mp4"
                fileName = "${URLDecoder.decode(titleParam, "UTF-8")}.$ext"
            }

            // Remove illegal file characters
            fileName = fileName.replace("[\\\\/*?:\"<>|]".toRegex(), "_")

            val downloadUri = Uri.parse(url)
            val request = DownloadManager.Request(downloadUri).apply {
                val cookie = CookieManager.getInstance().getCookie(url)
                if (!cookie.isNullOrEmpty()) {
                    addRequestHeader("Cookie", cookie)
                }
                if (!userAgent.isNullOrEmpty()) {
                    addRequestHeader("User-Agent", userAgent)
                }

                // Add referer for TikTok / Facebook streams if relevant
                if (url.contains("tiktok") || url.contains("byteoversea")) {
                    addRequestHeader("Referer", "https://www.tiktok.com/")
                } else if (url.contains("facebook") || url.contains("fbcdn")) {
                    addRequestHeader("Referer", "https://www.facebook.com/")
                }

                setTitle(fileName)
                setDescription("TaiMP4MP3 đang tải video về máy")
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                setAllowedOverMetered(true)
                setAllowedOverRoaming(true)

                // Save to /sdcard/Download/TaiMP4MP3/
                setDestinationInExternalPublicDir(
                    Environment.DIRECTORY_DOWNLOADS,
                    "TaiMP4MP3/$fileName"
                )
            }

            // Check write permission on older Android versions (<= Android 9)
            if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P) {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    != PackageManager.PERMISSION_GRANTED
                ) {
                    pendingDownloadRequest = request
                    requestStoragePermissionLauncher.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    return
                }
            }

            val downloadManager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            downloadManager.enqueue(request)
            Toast.makeText(this, getString(R.string.download_started, fileName), Toast.LENGTH_SHORT).show()

        } catch (e: Exception) {
            Toast.makeText(this, "Lỗi tải xuống: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun setupSwipeRefresh() {
        swipeRefreshLayout.setColorSchemeColors(
            ContextCompat.getColor(this, R.color.primary),
            ContextCompat.getColor(this, R.color.accent)
        )
        swipeRefreshLayout.setOnRefreshListener {
            webView.reload()
        }
    }

    private fun setupBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
    }

    private fun handleIntent(intent: Intent) {
        var targetUrl: String? = null

        // Handle shared URL from other apps (TikTok, YouTube, Facebook "Share" button)
        if (Intent.ACTION_SEND == intent.action && "text/plain" == intent.type) {
            val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
            if (!sharedText.isNullOrBlank()) {
                val pattern = Pattern.compile("https?://\\S+")
                val matcher = pattern.matcher(sharedText)
                if (matcher.find()) {
                    targetUrl = matcher.group()
                } else {
                    targetUrl = sharedText.trim()
                }
            }
        }

        val baseAssetUrl = "file:///android_asset/web/index.html"
        if (!targetUrl.isNullOrBlank()) {
            val encoded = URLEncoder.encode(targetUrl, "UTF-8")
            webView.loadUrl("$baseAssetUrl?url=$encoded")
        } else {
            webView.loadUrl(baseAssetUrl)
        }
    }
}
