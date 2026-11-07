/**
 * Callwise AI Receptionist - Embeddable Website Chat Widget
 * 
 * Usage:
 * <script src="https://your-domain.com/widget.js" data-callwise-key="cw_live_YOUR_KEY" defer></script>
 */

(function () {
  'use strict';

  // 1. Locate script tag and extract public key
  const scriptTag =
    document.currentScript ||
    document.querySelector('script[data-callwise-key]') ||
    document.querySelector('script[src*="widget.js"]');

  const publicKey =
    scriptTag?.getAttribute('data-callwise-key') ||
    window.CALLWISE_PUBLIC_KEY ||
    '';

  if (!publicKey) {
    console.warn('[Callwise Widget] Missing data-callwise-key attribute on script tag.');
    return;
  }

  // Determine iframe host URL from the script source
  let hostUrl = 'http://localhost:3000';
  if (scriptTag && scriptTag.src) {
    try {
      const url = new URL(scriptTag.src);
      hostUrl = url.origin;
    } catch (e) {
      // Fallback to current location or default
    }
  }

  // Prevent duplicate insertion
  if (document.getElementById('callwise-widget-container')) {
    return;
  }

  // 2. Create container DOM structure
  const container = document.createElement('div');
  container.id = 'callwise-widget-container';
  container.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 999999;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  `;

  // 3. Create floating launcher bubble button
  const bubble = document.createElement('button');
  bubble.id = 'callwise-launcher-bubble';
  bubble.setAttribute('aria-label', 'Open chat receptionist');
  bubble.style.cssText = `
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background-color: #2563EB;
    color: #ffffff;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease;
    outline: none;
  `;
  bubble.innerHTML = `
    <svg id="callwise-icon-chat" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
    <svg id="callwise-icon-close" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display: none;">
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>
  `;

  bubble.onmouseenter = () => (bubble.style.transform = 'scale(1.06)');
  bubble.onmouseleave = () => (bubble.style.transform = 'scale(1.0)');

  // 4. Create iframe popup window
  const iframeWrapper = document.createElement('div');
  iframeWrapper.id = 'callwise-iframe-wrapper';
  iframeWrapper.style.cssText = `
    display: none;
    position: absolute;
    bottom: 74px;
    right: 0;
    width: 380px;
    height: 580px;
    max-width: 90vw;
    max-height: 80vh;
    border-radius: 16px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.2);
    overflow: hidden;
    background: #ffffff;
    transition: opacity 0.2s ease, transform 0.2s ease;
    border: 1px solid rgba(0, 0, 0, 0.08);
  `;

  const iframe = document.createElement('iframe');
  iframe.src = `${hostUrl}/widget-frame/${encodeURIComponent(publicKey)}`;
  iframe.title = 'Callwise AI Chat Receptionist';
  iframe.style.cssText = `
    width: 100%;
    height: 100%;
    border: none;
    background: transparent;
  `;
  iframe.setAttribute('allow', 'clipboard-write');

  iframeWrapper.appendChild(iframe);
  container.appendChild(iframeWrapper);
  container.appendChild(bubble);
  document.body.appendChild(container);

  // 5. Toggle logic
  let isOpen = false;
  function toggleWidget() {
    isOpen = !isOpen;
    const chatIcon = document.getElementById('callwise-icon-chat');
    const closeIcon = document.getElementById('callwise-icon-close');

    if (isOpen) {
      iframeWrapper.style.display = 'block';
      if (chatIcon) chatIcon.style.display = 'none';
      if (closeIcon) closeIcon.style.display = 'block';
    } else {
      iframeWrapper.style.display = 'none';
      if (chatIcon) chatIcon.style.display = 'block';
      if (closeIcon) closeIcon.style.display = 'none';
    }
  }

  bubble.addEventListener('click', toggleWidget);

  // 6. Listen for postMessage events from the iframe (e.g. close, theme color update)
  window.addEventListener('message', function (event) {
    if (!event.data || typeof event.data !== 'object') return;
    if (event.data.type === 'CALLWISE_CLOSE_WIDGET') {
      if (isOpen) toggleWidget();
    }
    if (event.data.type === 'CALLWISE_SET_THEME_COLOR' && event.data.color) {
      bubble.style.backgroundColor = event.data.color;
    }
  });
})();
