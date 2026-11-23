// GitHub's /releases/latest omits prereleases. Select a published build with all three downloads.
async function updateDownloads() {
  const response = await fetch("https://api.github.com/repos/praha6248/PrismaFlow/releases?per_page=20");
  if (!response.ok) return;
  for (const release of await response.json()) {
    if (release.draft) continue;
    const asset = suffix => release.assets.find(file => file.state === "uploaded" && file.name.endsWith(suffix));
    const files = { windows: asset("-windows-x64-setup.exe"), linux: asset("-x86_64.AppImage"), archive: asset("-linux-x86_64.tar.gz") };
    if (!Object.values(files).every(Boolean)) continue;
    for (const [id, file] of Object.entries(files)) document.getElementById(id).href = file.browser_download_url;
    const version = document.getElementById("release");
    version.href = release.html_url;
    version.textContent = release.tag_name;
    return;
  }
}

updateDownloads().catch(() => { /* The static links remain usable when GitHub's API is offline. */ });
