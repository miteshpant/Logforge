'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { 
  Smartphone, 
  Download, 
  X, 
  Wifi, 
  WifiOff,
  Bell,
  Settings,
  Share
} from 'lucide-react'

interface PWASupportProps {
  className?: string
}

export const PWASupport: React.FC<PWASupportProps> = ({ className = '' }) => {
  const [isInstallable, setIsInstallable] = useState(false)
  const [isInstalled, setIsInstalled] = useState(false)
  const [isOnline, setIsOnline] = useState(true)
  const [showInstallPrompt, setShowInstallPrompt] = useState(false)
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null)
  const [isBrowser, setIsBrowser] = useState(false)
  const [canShare, setCanShare] = useState(false)
  const [notificationState, setNotificationState] = useState<'unavailable' | 'default' | 'granted' | 'denied'>('unavailable')

  useEffect(() => {
    // Mark that we're in browser environment
    setIsBrowser(true)

    // Check share capability
    if (typeof navigator !== 'undefined' && 'share' in navigator) {
      setCanShare(true)
    }

    // Check notification state
    if (typeof window !== 'undefined' && 'Notification' in window) {
      setNotificationState(Notification.permission as 'default' | 'granted' | 'denied')
    }

    // Check if app is already installed
    if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true)
    }

    // Listen for PWA install prompt
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e)
      setIsInstallable(true)
      setShowInstallPrompt(true)
    }

    // Listen for app installed event
    const handleAppInstalled = () => {
      setIsInstalled(true)
      setIsInstallable(false)
      setShowInstallPrompt(false)
      console.log('🎉 PWA installed successfully!')
    }

    // Listen for online/offline status
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleAppInstalled)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const handleInstallClick = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt()
      const { outcome } = await deferredPrompt.userChoice
      
      if (outcome === 'accepted') {
        console.log('✅ PWA installation accepted')
      } else {
        console.log('❌ PWA installation declined')
      }
      
      setDeferredPrompt(null)
      setShowInstallPrompt(false)
    }
  }

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Logforge Enterprise Platform',
          text: 'Advanced enterprise observability and SIEM platform',
          url: window.location.href,
        })
      } catch (error) {
        console.log('Share cancelled or failed:', error)
      }
    } else {
      // Fallback to clipboard
      navigator.clipboard.writeText(window.location.href)
      alert('Link copied to clipboard!')
    }
  }

  const requestNotificationPermission = async () => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      const permission = await Notification.requestPermission()
      setNotificationState(permission as 'default' | 'granted' | 'denied')
      if (permission === 'granted') {
        new Notification('Logforge Notifications Enabled', {
          body: 'You\'ll now receive real-time alerts and updates',
          icon: '/icon-192x192.png',
          badge: '/icon-192x192.png'
        })
      }
    }
  }

  return (
    <div className={className}>
      {/* Offline Indicator */}
      {!isOnline && (
        <div className="fixed top-0 left-0 right-0 bg-red-600 text-white text-center py-2 z-50" data-testid="offline-indicator">
          <div className="flex items-center justify-center space-x-2">
            <WifiOff className="w-4 h-4" />
            <span className="text-sm font-medium">You're offline - Some features may be limited</span>
          </div>
        </div>
      )}

      {/* PWA Install Prompt */}
      {showInstallPrompt && !isInstalled && (
        <Card className="fixed bottom-4 left-4 w-80 bg-gradient-to-r from-blue-600 to-purple-600 text-white border-0 shadow-2xl z-50 animate-in slide-in-from-bottom-4" data-testid="pwa-install-prompt">
          <CardContent className="p-4">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                  <Smartphone className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold">Install Logforge App</h3>
                  <p className="text-sm opacity-90">Get the full experience</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowInstallPrompt(false)}
                className="text-white hover:bg-white/20 w-8 h-8 p-0"
                data-testid="close-install-prompt"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
            
            <div className="space-y-2 mb-4">
              <div className="flex items-center space-x-2 text-sm">
                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                <span>Instant access from home screen</span>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                <span>Works offline with cached data</span>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                <span>Real-time notifications</span>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                <span>Native app experience</span>
              </div>
            </div>

            <div className="flex space-x-2">
              <Button
                onClick={handleInstallClick}
                className="flex-1 bg-blue-600 text-white hover:bg-blue-700"
                data-testid="install-pwa"
              >
                <Download className="w-4 h-4 mr-2" />
                Install
              </Button>
              <Button
                onClick={() => setShowInstallPrompt(false)}
                variant="outline"
                className="border-white/30 text-white hover:bg-white/10"
                data-testid="dismiss-install"
              >
                Later
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* PWA Status Indicator (when installed) */}
      {isInstalled && (
        <div className="fixed top-4 right-4 bg-green-600 text-white px-3 py-2 rounded-lg shadow-lg z-40" data-testid="pwa-installed-indicator">
          <div className="flex items-center space-x-2">
            <Smartphone className="w-4 h-4" />
            <span className="text-sm font-medium">PWA Mode</span>
          </div>
        </div>
      )}

      {/* PWA Controls (mobile-optimized) */}
      <div className="fixed bottom-4 left-4 flex flex-col space-y-2 md:hidden">
        {/* Notification Permission */}
        {isBrowser && !isInstalled && notificationState === 'default' && (
          <Button
            onClick={requestNotificationPermission}
            size="sm"
            className="bg-blue-600 hover:bg-blue-700 shadow-lg"
            data-testid="enable-notifications"
          >
            <Bell className="w-4 h-4 mr-2" />
            Enable Alerts
          </Button>
        )}

        {/* Share Button */}
        {isBrowser && canShare && (
          <Button
            onClick={handleShare}
            size="sm"
            variant="outline"
            className="bg-white/90 backdrop-blur-sm shadow-lg"
            data-testid="share-app"
          >
            <Share className="w-4 h-4 mr-2" />
            Share
          </Button>
        )}
      </div>
    </div>
  )
}

// PWA Manifest Configuration
export const PWAManifest = {
  name: 'Logforge Enterprise Platform',
  short_name: 'Logforge',
  description: 'Advanced enterprise observability and SIEM platform',
  start_url: '/',
  display: 'standalone',
  background_color: '#ffffff',
  theme_color: '#3b82f6',
  icons: [
    {
      src: '/icon-192x192.png',
      sizes: '192x192',
      type: 'image/png',
      purpose: 'any maskable'
    },
    {
      src: '/icon-512x512.png',
      sizes: '512x512',
      type: 'image/png',
      purpose: 'any maskable'
    }
  ],
  categories: ['business', 'productivity', 'utilities'],
  screenshots: [
    {
      src: '/screenshot-1.png',
      sizes: '1280x720',
      type: 'image/png',
      form_factor: 'wide'
    },
    {
      src: '/screenshot-2.png',
      sizes: '750x1334',
      type: 'image/png',
      form_factor: 'narrow'
    }
  ]
}

export default PWASupport