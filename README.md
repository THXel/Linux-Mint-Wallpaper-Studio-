<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Linux Mint Wallpaper Studio</title>
  <meta name="description" content="Linux Mint Wallpaper Studio – Animated wallpapers, playlists, preview and desktop integration for Linux Mint." />
  <style>
    :root {
      --bg: #07110d;
      --bg-soft: #0d1b15;
      --card: rgba(20, 36, 29, 0.82);
      --card-strong: rgba(26, 46, 37, 0.95);
      --text: #edf7f1;
      --muted: #b7ccc0;
      --line: rgba(150, 199, 173, 0.18);
      --accent: #7dd3a7;
      --accent-2: #34d399;
      --shadow: 0 20px 60px rgba(0,0,0,0.35);
      --radius: 22px;
      --max: 1180px;
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(52, 211, 153, 0.18), transparent 34%),
        radial-gradient(circle at 85% 10%, rgba(125, 211, 167, 0.12), transparent 24%),
        linear-gradient(180deg, #06100c 0%, #0a1511 100%);
      min-height: 100vh;
    }

    a { color: inherit; text-decoration: none; }

    .container {
      width: min(var(--max), calc(100% - 32px));
      margin: 0 auto;
    }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(16px);
      background: rgba(5, 11, 8, 0.7);
      border-bottom: 1px solid var(--line);
    }

    .nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 16px 0;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }

    .brand-badge {
      width: 42px;
      height: 42px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      font-size: 1.2rem;
      background: linear-gradient(135deg, rgba(125, 211, 167, 0.25), rgba(52, 211, 153, 0.12));
      border: 1px solid rgba(125, 211, 167, 0.25);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
    }

    .nav-links {
      display: flex;
      align-items: center;
      gap: 18px;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .nav-links a:hover { color: var(--text); }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 13px 18px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
      color: var(--text);
      font-weight: 600;
      transition: 0.2s ease;
    }

    .button:hover {
      transform: translateY(-1px);
      border-color: rgba(125, 211, 167, 0.4);
    }

    .button.primary {
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #072015;
      border-color: transparent;
      box-shadow: 0 12px 30px rgba(52, 211, 153, 0.24);
    }

    .hero {
      padding: 72px 0 42px;
    }

    .hero-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 32px;
      align-items: center;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      color: var(--accent);
      font-size: 0.88rem;
      margin-bottom: 18px;
    }

    h1 {
      margin: 0 0 18px;
      font-size: clamp(2.4rem, 6vw, 4.8rem);
      line-height: 1.02;
      letter-spacing: -0.04em;
    }

    .hero p {
      margin: 0;
      font-size: 1.08rem;
      line-height: 1.7;
      color: var(--muted);
      max-width: 700px;
    }

    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 28px;
    }

    .hero-card {
      background: linear-gradient(180deg, rgba(21, 39, 31, 0.88), rgba(14, 24, 20, 0.88));
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 22px;
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }

    .window {
      border-radius: 20px;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.06);
      background: #101a15;
    }

    .window-top {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 14px;
      background: #14221b;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: rgba(255,255,255,0.25);
    }

    .window-body {
      display: grid;
      grid-template-columns: 110px 1fr;
      min-height: 300px;
    }

    .sidebar {
      background: #0d1511;
      border-right: 1px solid rgba(255,255,255,0.05);
      padding: 14px;
      display: grid;
      gap: 10px;
      align-content: start;
    }

    .side-pill, .small-card, .feature, .step, .faq-item {
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
    }

    .side-pill {
      border-radius: 12px;
      padding: 10px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .preview {
      padding: 16px;
      display: grid;
      gap: 14px;
      background: linear-gradient(180deg, #101915 0%, #0b120f 100%);
    }

    .preview-banner {
      height: 132px;
      border-radius: 16px;
      background:
        linear-gradient(135deg, rgba(52, 211, 153, 0.25), rgba(125, 211, 167, 0.06)),
        linear-gradient(180deg, #1c3428 0%, #101915 100%);
      border: 1px solid rgba(255,255,255,0.06);
      position: relative;
      overflow: hidden;
    }

    .preview-banner::after {
      content: "Preview";
      position: absolute;
      right: 14px;
      bottom: 12px;
      font-size: 0.9rem;
      color: rgba(255,255,255,0.82);
      text-shadow: 0 1px 4px rgba(0,0,0,0.35);
    }

    .small-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .small-card {
      border-radius: 14px;
      padding: 14px;
      min-height: 82px;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .section {
      padding: 34px 0;
    }

    .section-header {
      margin-bottom: 22px;
      max-width: 760px;
    }

    .section-header h2 {
      margin: 0 0 10px;
      font-size: clamp(1.8rem, 3vw, 2.7rem);
      letter-spacing: -0.03em;
    }

    .section-header p {
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }

    .feature-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }

    .feature {
      border-radius: 20px;
      padding: 22px;
      background: linear-gradient(180deg, rgba(23, 39, 32, 0.92), rgba(15, 24, 20, 0.92));
      box-shadow: var(--shadow);
    }

    .feature h3 {
      margin: 0 0 10px;
      font-size: 1.05rem;
    }

    .feature p {
      margin: 0;
      color: var(--muted);
      line-height: 1.65;
      font-size: 0.96rem;
    }

    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }

    .panel {
      border-radius: 24px;
      padding: 22px;
      background: linear-gradient(180deg, rgba(21, 38, 31, 0.92), rgba(11, 20, 16, 0.92));
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }

    .steps {
      display: grid;
      gap: 14px;
    }

    .step {
      border-radius: 16px;
      padding: 16px;
      display: grid;
      grid-template-columns: 42px 1fr;
      gap: 14px;
      align-items: start;
    }

    .step-num {
      width: 42px;
      height: 42px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, rgba(125, 211, 167, 0.18), rgba(52, 211, 153, 0.08));
      color: var(--accent);
      font-weight: 800;
    }

    code {
      display: block;
      white-space: pre-wrap;
      word-break: break-word;
      background: rgba(0,0,0,0.26);
      border: 1px solid rgba(255,255,255,0.06);
      color: #d8f8e9;
      border-radius: 14px;
      padding: 14px;
      font-family: "Cascadia Code", "Fira Code", monospace;
      font-size: 0.92rem;
      line-height: 1.6;
      margin-top: 14px;
    }

    .screenshots {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    .shot {
      aspect-ratio: 16 / 10;
      border-radius: 22px;
      border: 1px solid var(--line);
      background:
        linear-gradient(135deg, rgba(52, 211, 153, 0.12), rgba(255,255,255,0.02)),
        linear-gradient(180deg, #182921, #0d1612);
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }

    .shot::before {
      content: attr(data-label);
      position: absolute;
      left: 14px;
      bottom: 12px;
      color: rgba(255,255,255,0.9);
      font-weight: 600;
      text-shadow: 0 1px 4px rgba(0,0,0,0.45);
    }

    .faq {
      display: grid;
      gap: 14px;
    }

    .faq-item {
      border-radius: 18px;
      padding: 18px;
      background: rgba(255,255,255,0.02);
    }

    .faq-item h3 {
      margin: 0 0 8px;
      font-size: 1rem;
    }

    .faq-item p {
      margin: 0;
      color: var(--muted);
      line-height: 1.65;
    }

    .footer {
      padding: 36px 0 52px;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .footer-box {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: center;
      border-top: 1px solid var(--line);
      padding-top: 22px;
      flex-wrap: wrap;
    }

    @media (max-width: 980px) {
      .hero-grid,
      .two-col,
      .feature-grid,
      .screenshots {
        grid-template-columns: 1fr;
      }

      .nav {
        flex-wrap: wrap;
      }

      .nav-links {
        width: 100%;
        justify-content: space-between;
        flex-wrap: wrap;
      }
    }

    @media (max-width: 640px) {
      .hero { padding-top: 44px; }
      .window-body { grid-template-columns: 1fr; }
      .sidebar { display: none; }
      .small-grid { grid-template-columns: 1fr; }
      .hero-actions, .footer-box { flex-direction: column; align-items: stretch; }
      .button { width: 100%; }
      .nav-links { gap: 12px; font-size: 0.9rem; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="container nav">
      <a href="#top" class="brand">
        <div class="brand-badge">🍃</div>
        <span>Linux Mint Wallpaper Studio</span>
      </a>
      <nav class="nav-links">
        <a href="#features">Features</a>
        <a href="#install">Installation</a>
        <a href="#screenshots">Screenshots</a>
        <a href="#faq">FAQ</a>
        <a href="https://github.com/USERNAME/REPOSITORY" class="button">GitHub</a>
      </nav>
    </div>
  </header>

  <main id="top">
    <section class="hero">
      <div class="container hero-grid">
        <div>
          <div class="eyebrow">Desktop wallpapers, playlists & preview for Linux Mint</div>
          <h1>Bring your desktop to life.</h1>
          <p>
            Linux Mint Wallpaper Studio is a clean and user-friendly way to manage animated wallpapers,
            preview them instantly, organize playlists and control how they behave on your desktop.
            Built for Linux Mint, designed to feel native.
          </p>
          <div class="hero-actions">
            <a class="button primary" href="https://github.com/USERNAME/REPOSITORY/releases">Download latest release</a>
            <a class="button" href="https://github.com/USERNAME/REPOSITORY">View on GitHub</a>
          </div>
        </div>

        <div class="hero-card">
          <div class="window">
            <div class="window-top">
              <div class="dot"></div>
              <div class="dot"></div>
              <div class="dot"></div>
            </div>
            <div class="window-body">
              <div class="sidebar">
                <div class="side-pill">Library</div>
                <div class="side-pill">Playlists</div>
                <div class="side-pill">Preview</div>
                <div class="side-pill">Settings</div>
              </div>
              <div class="preview">
                <div class="preview-banner"></div>
                <div class="small-grid">
                  <div class="small-card">Animated wallpapers with instant preview</div>
                  <div class="small-card">Playlist support and rotation controls</div>
                  <div class="small-card">Native-feeling Linux Mint style</div>
                  <div class="small-card">Simple setup and clean desktop integration</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="section" id="features">
      <div class="container">
        <div class="section-header">
          <h2>Made to be simple, polished and practical</h2>
          <p>
            The page is structured like a real project homepage: clear introduction, fast install steps,
            visual feature blocks and space for screenshots and release links.
          </p>
        </div>

        <div class="feature-grid">
          <article class="feature">
            <h3>Instant preview</h3>
            <p>Preview wallpapers quickly before applying them so the workflow stays fast and frustration-free.</p>
          </article>
          <article class="feature">
            <h3>Playlist management</h3>
            <p>Create and organize wallpaper playlists for automatic rotation and a more dynamic desktop setup.</p>
          </article>
          <article class="feature">
            <h3>Linux Mint focused</h3>
            <p>Designed around Linux Mint with a familiar visual language instead of a generic cross-platform look.</p>
          </article>
          <article class="feature">
            <h3>Beginner friendly</h3>
            <p>Download, install, launch and use it without digging through a complicated wall of documentation.</p>
          </article>
          <article class="feature">
            <h3>Modern UI</h3>
            <p>Dark Mint-inspired styling, soft cards and a clean layout that feels like a real product page.</p>
          </article>
          <article class="feature">
            <h3>Ready to expand</h3>
            <p>Add changelogs, screenshots, known issues, feature roadmaps or tutorial videos later without redesigning everything.</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section" id="install">
      <div class="container two-col">
        <div class="panel">
          <div class="section-header">
            <h2>Installation</h2>
            <p>Replace the placeholders below with your real repository and package names once everything is published.</p>
          </div>
          <div class="steps">
            <div class="step">
              <div class="step-num">1</div>
              <div>
                <strong>Download the latest release</strong>
                <p>Get the newest <code>.deb</code> package from the GitHub releases page.</p>
              </div>
            </div>
            <div class="step">
              <div class="step-num">2</div>
              <div>
                <strong>Install with APT or DPKG</strong>
                <code>cd ~/Downloads
sudo dpkg -i mint-wallpaper-studio_VERSION_all.deb
sudo apt -f install</code>
              </div>
            </div>
            <div class="step">
              <div class="step-num">3</div>
              <div>
                <strong>Launch the app</strong>
                <code>mint-wallpaper-studio</code>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="section-header">
            <h2>Why this layout works well on GitHub Pages</h2>
            <p>It looks much more professional than a plain README while still staying lightweight and easy to host.</p>
          </div>
          <div class="steps">
            <div class="step">
              <div class="step-num">A</div>
              <div><strong>Fast first impression</strong><p>Visitors instantly understand what the project does and where to download it.</p></div>
            </div>
            <div class="step">
              <div class="step-num">B</div>
              <div><strong>Better screenshots</strong><p>The page leaves dedicated space for UI screenshots instead of burying them in text.</p></div>
            </div>
            <div class="step">
              <div class="step-num">C</div>
              <div><strong>Scales with the project</strong><p>You can later add release notes, setup tips, FAQs and links to documentation sections.</p></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="section" id="screenshots">
      <div class="container">
        <div class="section-header">
          <h2>Screenshots</h2>
          <p>
            These are placeholders right now. We can swap them next with your actual screenshots from the app UI,
            downloads page, preview section or playlist manager.
          </p>
        </div>
        <div class="screenshots">
          <div class="shot" data-label="Main window"></div>
          <div class="shot" data-label="Wallpaper preview"></div>
          <div class="shot" data-label="Playlist manager"></div>
        </div>
      </div>
    </section>

    <section class="section" id="faq">
      <div class="container">
        <div class="section-header">
          <h2>FAQ</h2>
          <p>Starter questions for the page. These can be adjusted once your public release flow is final.</p>
        </div>
        <div class="faq">
          <div class="faq-item">
            <h3>Does it only work on Linux Mint?</h3>
            <p>Right now the page is written with Linux Mint as the primary target. We can later add a compatibility section if needed.</p>
          </div>
          <div class="faq-item">
            <h3>How do I install updates?</h3>
            <p>Download the latest release package and install it over the current version, or add an update section later if you automate releases.</p>
          </div>
          <div class="faq-item">
            <h3>Can I create wallpaper playlists?</h3>
            <p>Yes — this section is already ready for that message, and we can expand it with exact behavior and supported features.</p>
          </div>
        </div>
      </div>
    </section>
  </main>

  <footer class="footer">
    <div class="container footer-box">
      <div>Linux Mint Wallpaper Studio — open source desktop wallpaper manager for Linux Mint.</div>
      <div>
        <a href="https://github.com/USERNAME/REPOSITORY">Repository</a>
        ·
        <a href="https://github.com/USERNAME/REPOSITORY/releases">Releases</a>
      </div>
    </div>
  </footer>
</body>
</html>
