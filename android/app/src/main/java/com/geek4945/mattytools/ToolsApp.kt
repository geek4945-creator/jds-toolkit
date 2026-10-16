package com.geek4945.mattytools

import android.app.Application
import com.geek4945.mattytools.data.CatalogRepository
import com.geek4945.mattytools.work.UpdateWorker

class ToolsApp : Application() {
    lateinit var repo: CatalogRepository
        private set

    override fun onCreate() {
        super.onCreate()
        repo = CatalogRepository(this)
        UpdateWorker.ensureChannel(this)
        UpdateWorker.schedule(this)
    }
}
