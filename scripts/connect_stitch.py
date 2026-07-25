import os
import re

STITCH_DIR = 'stitch_aether_ai_operating_system'
WEB_DIR = 'web'

PAGES = {
    'index.html': ('aetheros_desktop', 'dashboard'),
    'agents.html': ('aetheros_agents_control', 'agents'),
    'memory.html': ('aetheros_memory_intelligence_system', 'memory'),
    'control.html': ('jarvis_mission_control_dashboard', 'control'),
    'browser.html': ('aetheros_computer_vision_intelligence', 'browser'),
    'terminal.html': ('aetheros_voice_interaction', 'terminal'),
    'automation.html': ('aetheros_automation_dashboard', 'automation'),
    'settings.html': ('aetheros_advanced_settings_hub', 'settings'),
    'planning.html': ('aetheros_autonomous_planning_hub', 'planning')
}

# The Files page is basically the desktop layout but with a custom center canvas showing files
PAGES['files.html'] = ('aetheros_desktop', 'files')

# Navigation links template
NAV_TEMPLATE = """
<div class="flex-1 overflow-y-auto px-4 flex flex-col gap-1">
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_dashboard}" href="/index.html">
        <span class="material-symbols-outlined">dashboard</span>
        Dashboard
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_agents}" href="/agents.html">
        <span class="material-symbols-outlined">smart_toy</span>
        Agents
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_memory}" href="/memory.html">
        <span class="material-symbols-outlined">memory</span>
        Memory
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_control}" href="/control.html">
        <span class="material-symbols-outlined">settings_remote</span>
        Control
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_browser}" href="/browser.html">
        <span class="material-symbols-outlined">language</span>
        Browser
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_files}" href="/files.html">
        <span class="material-symbols-outlined">folder_open</span>
        Files
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_terminal}" href="/terminal.html">
        <span class="material-symbols-outlined">terminal</span>
        Terminal
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_automation}" href="/automation.html">
        <span class="material-symbols-outlined">bolt</span>
        Automation
    </a>
    <a class="flex items-center gap-3 py-2 pl-4 transition-all hover:scale-102 duration-300 font-body-md {active_settings}" href="/settings.html">
        <span class="material-symbols-outlined">settings</span>
        Settings
    </a>
</div>
"""

# Unified sidebar template based on aetheros_desktop
SIDEBAR_TEMPLATE = """
<aside class="fixed left-0 top-16 bottom-0 flex flex-col py-stack-md bg-surface-container/10 dark:bg-surface-container-lowest/10 backdrop-blur-2xl border-r border-white/5 shadow-[64px_0_64px_-20px_rgba(0,0,0,0.4)] h-full w-64 z-40 hidden md:flex">
    <!-- Header -->
    <div class="px-container-padding mb-8 flex flex-col items-center justify-center pt-4">
        <div class="w-16 h-16 rounded-full glass-card flex items-center justify-center mb-4 relative">
            <div class="absolute inset-2 rounded-full bg-gradient-to-tr from-primary to-secondary-fixed opacity-50 blur-sm animate-pulse"></div>
            <span class="material-symbols-outlined text-primary relative z-10" style="font-size: 32px;">graphic_eq</span>
        </div>
        <h2 class="font-display-lg text-headline-sm text-primary">Aether Core</h2>
        <span class="text-label-md font-label-md text-secondary-fixed-dim mt-1">V4.2 Active</span>
    </div>
    <!-- Tabs -->
    {navigation}
    <!-- Footer / CTA -->
    <div class="px-4 mt-auto pt-4 border-t border-white/5 pb-20">
        <button class="w-full py-2 mb-4 rounded-lg border border-white/10 text-on-surface hover:bg-white/5 transition-colors font-body-md flex items-center justify-center gap-2">
            <span class="material-symbols-outlined" style="font-size: 18px;">add</span>
            New Thread
        </button>
        <div class="flex justify-between px-2 text-label-md font-label-md text-on-surface-variant">
            <div class="flex items-center gap-1">
                <span class="material-symbols-outlined" style="font-size: 14px;">sensors</span>
                Status
            </div>
            <div class="flex items-center gap-1">
                <span class="material-symbols-outlined" style="font-size: 14px;">timer</span>
                Uptime
            </div>
        </div>
    </div>
</aside>
"""

# Script to inject into every page
GLOBAL_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'global_script.js')
if os.path.exists(GLOBAL_SCRIPT_PATH):
    with open(GLOBAL_SCRIPT_PATH, 'r', encoding='utf-8') as f:
        GLOBAL_SCRIPT = f"<script>\n{f.read()}\n</script>"
else:
    GLOBAL_SCRIPT = ""

def process_html_file(file_name, source_folder, tab_name):
    source_path = os.path.join(STITCH_DIR, source_folder, 'code.html')
    dest_path = os.path.join(WEB_DIR, file_name)
    
    if not os.path.exists(source_path):
        print(f"Warning: {source_path} does not exist!")
        return

    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Determine active classes
    active_dashboard = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'dashboard' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_agents = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'agents' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_memory = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'memory' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_control = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'control' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_browser = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'browser' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_files = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'files' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_terminal = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'terminal' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_automation = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'automation' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"
    active_settings = "text-secondary-fixed bg-white/5 border-l-2 border-secondary-fixed-dim pl-4" if tab_name == 'settings' else "text-on-surface-variant hover:text-on-surface hover:bg-white/5"

    nav_rendered = NAV_TEMPLATE.format(
        active_dashboard=active_dashboard,
        active_agents=active_agents,
        active_memory=active_memory,
        active_control=active_control,
        active_browser=active_browser,
        active_files=active_files,
        active_terminal=active_terminal,
        active_automation=active_automation,
        active_settings=active_settings
    )

    sidebar_rendered = SIDEBAR_TEMPLATE.format(navigation=nav_rendered)

    # 1. Completely replace the aside/nav element with our unified sidebar_rendered
    # Matches <aside ...>...</aside> or <nav class="hidden md:flex flex-col...`
    content = re.sub(
        r'<(aside|nav) class="[^"]*(fixed left-0|left-0 top-16|hidden md:flex flex-col bg-white)[^"]*">.*?</\1>',
        sidebar_rendered,
        content,
        flags=re.DOTALL
    )

    # 2. Modify specific pages to be interactive
    if tab_name == 'memory':
        # Add input class / custom trigger buttons
        content = content.replace('placeholder="Recall keywords..."', 'placeholder="Recall keywords..." id="mem-query"')
        content = content.replace('placeholder="Fact statement..."', 'placeholder="Fact statement..." id="mem-fact"')
        # Inject custom classes to match JS triggers
        content = content.replace('Save Memory', 'Save Memory" class="memory-save-trigger')

    elif tab_name == 'files':
        # Overwrite center canvas of aetheros_desktop with a file editor UI
        files_canvas = """
        <main class="flex-1 ml-0 md:ml-64 flex flex-row relative z-10 h-full w-full">
            <div class="w-80 border-r border-white/5 bg-surface-container/10 p-6 flex flex-col gap-4 overflow-y-auto h-full files-list-container">
                <!-- Live files list will load here -->
            </div>
            <div class="flex-1 flex flex-col h-full overflow-hidden">
                <div class="border-b border-white/5 p-4 bg-black/20 font-label-md text-label-md text-primary">
                    File Editor / Reader
                </div>
                <pre class="flex-1 p-6 font-label-md text-label-md text-on-surface-variant bg-black/40 overflow-auto whitespace-pre-wrap editor-content-area">Select a file from the sidebar to inspect its contents.</pre>
            </div>
        </main>
        """
        # Replace the main area
        content = re.sub(r'<main class="flex-1 ml-0 md:ml-64 flex flex-col relative z-10 h-full max-w-5xl mx-auto w-full">.*?</main>', files_canvas, content, flags=re.DOTALL)

    # 3. Inject our global script just before </body>
    content = content.replace('</body>', GLOBAL_SCRIPT + '</body>')

    # Save processed HTML file
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Processed and created {dest_path}")

def main():
    print("Connecting Stitch frontend to VEGAS API backend...")
    for file_name, (folder, tab) in PAGES.items():
        process_html_file(file_name, folder, tab)
    print("Done!")

if __name__ == '__main__':
    main()
