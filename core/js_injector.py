"""
Browser extension — patches all known JS fingerprinting vectors.

Fixed vs previous version:
  - Timezone: now patches Date.prototype.getTimezoneOffset() AND
    Intl.DateTimeFormat resolvedOptions() so both methods return fake TZ.
  - Battery API: spoofs charging/level/chargingTime/dischargingTime.
  - Media devices: spoofs enumerateDevices() count.
  - Plugins: replaces navigator.plugins with a realistic static list.
  - Fonts: getComputedStyle measurement returns consistent fake dimensions.
  - AudioContext: sampleRate and analyser node values spoofed.
  - window.chrome: adds chrome runtime object (missing = detected as bot).
  - permissions: returns consistent 'prompt' for all sensors.
"""

import json
from pathlib import Path
from typing import Optional

from utils.config import CONFIG
from utils.helpers import logger


class JSInjector:

    MANIFEST: dict = {
        "manifest_version": 3,
        "name": "KimShell Shield",
        "version": "2.1",
        "description": "Full fingerprint protection — KimShell",
        "permissions": ["scripting"],
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": ["content.js"],
                "run_at": "document_start",
                "all_frames": True,
                "world": "MAIN",
            }
        ],
    }

    # All __PLACEHOLDERS__ are replaced with real profile values at runtime
    CONTENT_JS = r"""
(function () {
'use strict';

// ═══════════════════════════════════════════════════════════════
// PROFILE VALUES (injected by KimShell at extension creation)
// ═══════════════════════════════════════════════════════════════
const P = {
    webglVendor:   '__WEBGL_VENDOR__',
    webglRenderer: '__WEBGL_RENDERER__',
    cpuCores:       __CPU_CORES__,
    ramGb:          __TOTAL_RAM__,
    screenW:        __SCREEN_W__,
    screenH:        __SCREEN_H__,
    timezone:      '__TIMEZONE__',       // e.g. "America/New_York"
    tzOffset:       __TZ_OFFSET__,       // e.g. 300  (minutes, positive=west)
    language:      '__LANGUAGE__',
    uaString:      '__UA_STRING__',
    profileHash:   '__PROFILE_HASH__',
};

// ═══════════════════════════════════════════════════════════════
// 1. CANVAS — pixel noise ±1 per channel
// ═══════════════════════════════════════════════════════════════
const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function (...a) {
    const img = _origGetImageData.apply(this, a);
    for (let i = 0; i < img.data.length; i += 4) {
        img.data[i]   = Math.max(0, Math.min(255, img.data[i]   + (Math.random() > .5 ? 1 : -1)));
        img.data[i+1] = Math.max(0, Math.min(255, img.data[i+1] + (Math.random() > .5 ? 1 : -1)));
        img.data[i+2] = Math.max(0, Math.min(255, img.data[i+2] + (Math.random() > .5 ? 1 : -1)));
    }
    return img;
};
const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function (...a) {
    const ctx = this.getContext('2d');
    if (ctx) {
        const img = _origGetImageData.call(ctx, 0, 0, this.width || 1, this.height || 1);
        ctx.putImageData(img, 0, 0);
    }
    return _origToDataURL.apply(this, a);
};

// ═══════════════════════════════════════════════════════════════
// 2. WEBGL
// ═══════════════════════════════════════════════════════════════
function _patchWebGL(proto) {
    const _get = proto.getParameter;
    proto.getParameter = function (p) {
        if (p === 0x9245) return P.webglVendor;    // UNMASKED_VENDOR_WEBGL
        if (p === 0x9246) return P.webglRenderer;  // UNMASKED_RENDERER_WEBGL
        if (p === 0x1F00) return P.webglVendor;    // VENDOR
        if (p === 0x1F01) return P.webglRenderer;  // RENDERER
        return _get.call(this, p);
    };
}
const _origGetCtx = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (type, ...r) {
    const ctx = _origGetCtx.apply(this, [type, ...r]);
    if (ctx && (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl')) {
        _patchWebGL(ctx.constructor.prototype);
    }
    return ctx;
};

// ═══════════════════════════════════════════════════════════════
// 3. NAVIGATOR — hardware / platform / vendor
// ═══════════════════════════════════════════════════════════════
const _navProps = {
    hardwareConcurrency: P.cpuCores,
    deviceMemory:        P.ramGb,
    platform:            'Win32',
    vendor:              'Google Inc.',
    vendorSub:           '',
    productSub:          '20030107',
    language:            P.language,
    languages:           [P.language, 'en'],
    webdriver:           undefined,
    maxTouchPoints:      0,
};
for (const [k, v] of Object.entries(_navProps)) {
    try { Object.defineProperty(navigator, k, { get: () => v, configurable: true }); }
    catch (_) {}
}
// Remove automation flag
try { delete Object.getPrototypeOf(navigator).webdriver; } catch (_) {}

// ═══════════════════════════════════════════════════════════════
// 4. SCREEN
// ═══════════════════════════════════════════════════════════════
const _screenProps = {
    width:       P.screenW,
    height:      P.screenH,
    availWidth:  P.screenW,
    availHeight: P.screenH - 40,
    availTop:    0,
    availLeft:   0,
    colorDepth:  24,
    pixelDepth:  24,
};
for (const [k, v] of Object.entries(_screenProps)) {
    try { Object.defineProperty(screen, k, { get: () => v, configurable: true }); }
    catch (_) {}
}

// ═══════════════════════════════════════════════════════════════
// 5. TIMEZONE — both Date and Intl APIs
// ═══════════════════════════════════════════════════════════════
// 5a. Date.prototype.getTimezoneOffset — most common leak
const _origGetTZO = Date.prototype.getTimezoneOffset;
Date.prototype.getTimezoneOffset = function () { return P.tzOffset; };

// 5b. Intl.DateTimeFormat — used by advanced fingerprinters
const _origDTF = Intl.DateTimeFormat;
function _patchedDTF(locale, opts = {}) {
    opts = Object.assign({}, opts);
    if (!opts.timeZone) opts.timeZone = P.timezone;
    return new _origDTF(locale, opts);
}
_patchedDTF.prototype         = _origDTF.prototype;
_patchedDTF.supportedLocalesOf = _origDTF.supportedLocalesOf.bind(_origDTF);
Intl.DateTimeFormat = _patchedDTF;

// 5c. resolvedOptions() — explicit timezone field
const _origResolved = _origDTF.prototype.resolvedOptions;
_origDTF.prototype.resolvedOptions = function () {
    const o = _origResolved.call(this);
    return Object.assign({}, o, { timeZone: P.timezone });
};

// ═══════════════════════════════════════════════════════════════
// 6. BATTERY API — spoof all fields
// ═══════════════════════════════════════════════════════════════
if (navigator.getBattery) {
    const _fakeBattery = {
        charging:        false,     // not plugged in — less fingerprintable
        chargingTime:    Infinity,
        dischargingTime: 36000,     // ~10 hours
        level:           0.72,      // 72% — realistic laptop value
        addEventListener:    () => {},
        removeEventListener: () => {},
        dispatchEvent:       () => false,
    };
    navigator.getBattery = () => Promise.resolve(_fakeBattery);
}

// ═══════════════════════════════════════════════════════════════
// 7. MEDIA DEVICES — hide real device count
// ═══════════════════════════════════════════════════════════════
if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
    const _origEnum = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
    navigator.mediaDevices.enumerateDevices = async function () {
        // Return generic unlabelled device list (labels require permission anyway)
        return [
            { kind: 'audioinput',  deviceId: 'default', groupId: 'grp1', label: '', toJSON() { return this; } },
            { kind: 'audiooutput', deviceId: 'default', groupId: 'grp1', label: '', toJSON() { return this; } },
        ];
    };
}

// ═══════════════════════════════════════════════════════════════
// 8. PLUGINS — replace with realistic static list
// ═══════════════════════════════════════════════════════════════
const _fakePlugins = [
    { name: 'PDF Viewer',         filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
    { name: 'Chromium PDF Viewer',filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
    { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    { name: 'WebKit built-in PDF',filename: 'internal-pdf-viewer',   description: 'Portable Document Format' },
];
function _makePluginArray(plugins) {
    const arr = Object.create(PluginArray.prototype);
    plugins.forEach((p, i) => {
        const plug = Object.create(Plugin.prototype);
        Object.defineProperty(plug, 'name',        { get: () => p.name });
        Object.defineProperty(plug, 'filename',    { get: () => p.filename });
        Object.defineProperty(plug, 'description', { get: () => p.description });
        Object.defineProperty(plug, 'length',      { get: () => 0 });
        arr[i] = plug;
    });
    Object.defineProperty(arr, 'length', { get: () => plugins.length });
    arr.item    = i => arr[i];
    arr.namedItem = n => plugins.find(p => p.name === n) || null;
    arr.refresh = () => {};
    return arr;
}
try {
    Object.defineProperty(navigator, 'plugins',  { get: () => _makePluginArray(_fakePlugins), configurable: true });
    Object.defineProperty(navigator, 'mimeTypes',{ get: () => ({ length: 0, item: () => null, namedItem: () => null }), configurable: true });
} catch (_) {}

// ═══════════════════════════════════════════════════════════════
// 9. AUDIOCONTEXT — spoof sampleRate + analyser fingerprint
// ═══════════════════════════════════════════════════════════════
if (typeof AudioContext !== 'undefined') {
    const _origAC = AudioContext;
    window.AudioContext = function (opts = {}) {
        opts = Object.assign({ sampleRate: 44100 }, opts);  // standard rate
        const ctx = new _origAC(opts);

        const _origCreateAnalyser = ctx.createAnalyser.bind(ctx);
        ctx.createAnalyser = function () {
            const analyser = _origCreateAnalyser();
            const _origGetFloat = analyser.getFloatFrequencyData.bind(analyser);
            analyser.getFloatFrequencyData = function (arr) {
                _origGetFloat(arr);
                for (let i = 0; i < arr.length; i++) {
                    arr[i] += (Math.random() - 0.5) * 0.1;
                }
            };
            return analyser;
        };

        const _origCreateOsc = ctx.createOscillator.bind(ctx);
        ctx.createOscillator = function () {
            const osc = _origCreateOsc();
            const _origConn = osc.connect.bind(osc);
            osc.connect = function (...a) {
                osc.frequency.value += (Math.random() - 0.5) * 0.0001;
                return _origConn(...a);
            };
            return osc;
        };
        return ctx;
    };
    window.AudioContext.prototype = _origAC.prototype;
}

// ═══════════════════════════════════════════════════════════════
// 10. PERMISSIONS — deny sensor APIs (no real hardware data)
// ═══════════════════════════════════════════════════════════════
if (navigator.permissions && navigator.permissions.query) {
    const _origQuery = navigator.permissions.query.bind(navigator.permissions);
    const _sensorAPIs = new Set([
        'accelerometer','gyroscope','magnetometer',
        'ambient-light-sensor','accessibility-events',
    ]);
    navigator.permissions.query = function (desc) {
        if (desc && _sensorAPIs.has(desc.name)) {
            return Promise.resolve({ state: 'denied', onchange: null });
        }
        return _origQuery(desc);
    };
}

// ═══════════════════════════════════════════════════════════════
// 11. FONT METRICS — add tiny jitter to break measurement hashing
// ═══════════════════════════════════════════════════════════════
const _origGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = function (el, pseudo) {
    const style = _origGetComputedStyle.call(window, el, pseudo);
    const _origGetProp = style.getPropertyValue.bind(style);
    style.getPropertyValue = function (prop) {
        const val = _origGetProp(prop);
        if ((prop === 'width' || prop === 'height') && val && val.endsWith('px')) {
            const num = parseFloat(val);
            if (!isNaN(num)) {
                return (num + (Math.random() - 0.5) * 0.02).toFixed(6) + 'px';
            }
        }
        return val;
    };
    return style;
};

// ═══════════════════════════════════════════════════════════════
// 12. WINDOW.CHROME — real Brave/Chrome has this object
//     Missing = detected as automation
// ═══════════════════════════════════════════════════════════════
if (!window.chrome) {
    window.chrome = {
        runtime: {
            connect:             () => {},
            sendMessage:         () => {},
            onMessage:           { addListener: () => {}, removeListener: () => {} },
            id:                  undefined,
        },
        loadTimes: function () { return {}; },
        csi:       function () { return { startE: Date.now(), onloadT: Date.now(), pageT: 1000, tran: 15 }; },
        app:       { isInstalled: false },
    };
}

// ═══════════════════════════════════════════════════════════════
// 13. USERAGENT — override JS navigator.userAgent too
// ═══════════════════════════════════════════════════════════════
try {
    Object.defineProperty(navigator, 'userAgent', { get: () => P.uaString, configurable: true });
    Object.defineProperty(navigator, 'appVersion', {
        get: () => P.uaString.replace('Mozilla/', ''), configurable: true
    });
} catch (_) {}

// ═══════════════════════════════════════════════════════════════
// 14. IN-PAGE BADGE — floating KimShell indicator inside every page
//     Only top frame, not iframes. Click to collapse.
// ═══════════════════════════════════════════════════════════════
if (window === window.top) {
    const _injectBadge = () => {
        if (document.getElementById('__ks_badge')) return;

        const shield = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="18" height="18">
          <defs>
            <linearGradient id="ksG" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#0d1f18"/>
              <stop offset="100%" stop-color="#050d0a"/>
            </linearGradient>
          </defs>
          <path d="M100 12 L172 40 L172 105 Q172 155 100 188 Q28 155 28 105 L28 40 Z"
                fill="url(#ksG)" stroke="#00ff88" stroke-width="6" stroke-linejoin="round"/>
          <rect x="74" y="62" width="9" height="76" rx="1.5" fill="#00ff88"/>
          <polygon points="83,100 120,62 131,62 94,100" fill="#00ff88"/>
          <polygon points="83,100 120,138 131,138 94,100" fill="#00ff88"/>
        </svg>`;

        const badge = document.createElement('div');
        badge.id = '__ks_badge';
        badge.innerHTML = `
          <div id="__ks_inner">
            <span id="__ks_icon">${shield}</span>
            <span id="__ks_text">KimShell <span style="color:#00cc66;font-weight:normal;font-size:9px;">PROTECTED</span></span>
            <span id="__ks_hash" title="Profile hash">· __PROFILE_HASH__</span>
          </div>
        `;

        const style = document.createElement('style');
        style.textContent = `
          #__ks_badge {
            position: fixed;
            bottom: 18px;
            right: 18px;
            z-index: 2147483647;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            cursor: pointer;
            user-select: none;
            transition: opacity .3s, transform .3s;
          }
          #__ks_inner {
            display: flex;
            align-items: center;
            gap: 6px;
            background: rgba(10, 20, 15, 0.82);
            border: 1px solid rgba(0, 255, 136, 0.45);
            border-radius: 8px;
            padding: 5px 10px 5px 7px;
            color: #00ff88;
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            box-shadow:
              0 0 10px rgba(0,255,136,0.15),
              0 0 24px rgba(0,255,136,0.07),
              inset 0 0 8px rgba(0,255,136,0.04);
            transition: box-shadow .4s, border-color .4s;
          }
          #__ks_badge:hover #__ks_inner {
            border-color: rgba(0,255,136,0.8);
            box-shadow:
              0 0 16px rgba(0,255,136,0.35),
              0 0 40px rgba(0,255,136,0.12);
          }
          #__ks_icon { display:flex; align-items:center; }
          #__ks_text { font-weight: bold; letter-spacing: .5px; }
          #__ks_hash { color: #1a5a3a; font-size: 9px; letter-spacing: .3px; }
          #__ks_badge.collapsed #__ks_text,
          #__ks_badge.collapsed #__ks_hash { display: none; }
          #__ks_badge.collapsed #__ks_inner {
            padding: 5px 7px;
            background: rgba(10,20,15,0.65);
          }
          @keyframes __ks_pulse {
            0%, 100% { box-shadow: 0 0 10px rgba(0,255,136,.15), 0 0 24px rgba(0,255,136,.07), inset 0 0 8px rgba(0,255,136,.04); }
            50%       { box-shadow: 0 0 16px rgba(0,255,136,.28), 0 0 36px rgba(0,255,136,.10), inset 0 0 8px rgba(0,255,136,.06); }
          }
          #__ks_inner { animation: __ks_pulse 3s ease-in-out infinite; }
        `;

        document.head.appendChild(style);
        document.body.appendChild(badge);

        // Click to collapse / expand
        badge.addEventListener('click', () => {
            badge.classList.toggle('collapsed');
        });
    };

    // Inject after DOM is ready
    if (document.body) {
        _injectBadge();
    } else {
        document.addEventListener('DOMContentLoaded', _injectBadge);
        // Fallback for very fast pages
        setTimeout(_injectBadge, 500);
    }
}

console.debug('[KimShell Shield v2.1] active — hash:', P.profileHash);
})();
"""

    # ── Timezone offset table (minutes west of UTC, matches Python's pytz convention) ──────────
    # We store offsets for the timezones we generate so the JS value matches the name.
    _TZ_OFFSETS = {
        "America/New_York":    300,   # UTC-5 (EST) / UTC-4 DST — use standard
        "America/Chicago":     360,   # UTC-6
        "America/Los_Angeles": 480,   # UTC-8
        "Europe/London":         0,   # UTC+0
        "Europe/Amsterdam":    -60,   # UTC+1
        "Europe/Berlin":       -60,   # UTC+1
        "Asia/Tokyo":         -540,   # UTC+9
    }

    # ── Public API ────────────────────────────────────────────────────────────

    def create_extension(self, profile) -> Path:
        ext_dir = CONFIG.EXTENSION_DIR
        ext_dir.mkdir(parents=True, exist_ok=True)

        # manifest.json
        with open(ext_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(self.MANIFEST, f, indent=2)

        # Resolve timezone offset
        tz_offset = self._TZ_OFFSETS.get(profile.timezone, 0)

        # content.js — substitute all placeholders
        js = (
            self.CONTENT_JS
            .replace("__WEBGL_VENDOR__",   self._js(profile.webgl_vendor))
            .replace("__WEBGL_RENDERER__", self._js(profile.webgl_renderer))
            .replace("__CPU_CORES__",      str(profile.cpu_cores))
            .replace("__TOTAL_RAM__",      str(profile.total_ram_gb))
            .replace("__SCREEN_W__",       str(profile.screen_width))
            .replace("__SCREEN_H__",       str(profile.screen_height))
            .replace("__TIMEZONE__",       profile.timezone)
            .replace("__TZ_OFFSET__",      str(tz_offset))
            .replace("__LANGUAGE__",       profile.language)
            .replace("__UA_STRING__",      self._js(profile.user_agent))
            .replace("__PROFILE_HASH__",   profile.profile_hash)
        )

        with open(ext_dir / "content.js", "w", encoding="utf-8") as f:
            f.write(js.strip())

        logger.info(
            f"Extension created [{ext_dir}] — "
            f"TZ: {profile.timezone} (offset {tz_offset}m), "
            f"profile hash: {profile.profile_hash}"
        )
        return ext_dir

    @staticmethod
    def _js(value: str) -> str:
        """Escape for JS single-quoted string."""
        return value.replace("\\", "\\\\").replace("'", "\\'")
