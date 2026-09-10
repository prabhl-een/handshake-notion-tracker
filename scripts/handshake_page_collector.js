/**
 * handshake_page_collector.js
 *
 * Run this in your browser's DevTools Console while logged into Handshake,
 * on your "Saved Jobs" page. It automatically clicks through every page of
 * results, collecting BOTH the visible page text (for title/company/
 * deadline parsing) AND each job's real URL (read directly from the link
 * already in the page's HTML -- no clicking into individual jobs). It
 * downloads two files when done:
 *   - handshake_saved_jobs_raw.txt  -> feed to `python src/main.py parse`
 *   - handshake_urls.json           -> feed to `python src/merge_urls.py`
 *
 * WHY THIS APPROACH (and not a login bot):
 * This runs inside YOUR OWN authenticated browser tab. It never touches or
 * stores your password, and there's no separate automated login step -- it
 * only automates clicking a button you'd otherwise click yourself, and
 * reads links already present in the page's HTML (nothing is clicked or
 * fetched beyond the "next page" button). That's a meaningfully lower-risk
 * category than a headless script that logs in on its own, or one that
 * clicks into every individual job -- though it's still automated
 * interaction with the page, so use your own judgment about Handshake's
 * terms of service.
 *
 * HOW TO USE:
 *   1. Go to your Handshake "Saved Jobs" page (make sure you're on page 1).
 *   2. Open DevTools (F12, or right-click > Inspect) and click the "Console" tab.
 *   3. Paste this entire script in and press Enter (type "allow pasting"
 *      first if your browser blocks it).
 *   4. Watch it click through pages automatically (it waits 2s between each
 *      to let content load -- adjust PAGE_LOAD_DELAY_MS below if your
 *      connection is slower and pages aren't fully loaded before it grabs text).
 *   5. When it finishes, both files download automatically.
 *
 * IF THE "NEXT PAGE" BUTTON ISN'T FOUND:
 *   Handshake's exact button markup can change. If the script stops after
 *   page 1 and you know there are more pages, right-click the ">" / "Next"
 *   pagination control on the page, choose "Inspect," and look at the
 *   highlighted HTML element. Update NEXT_BUTTON_SELECTORS below to match
 *   (e.g. add its class name or aria-label).
 */

(async function collectHandshakeSavedJobs() {
  const PAGE_LOAD_DELAY_MS = 2000;
  const MAX_PAGES = 25; // safety cap so a stuck selector can't loop forever

  // Tried in order; the first one that matches a clickable, non-disabled
  // element on the page wins. Add more candidates here if needed.
  const NEXT_BUTTON_SELECTORS = [
    'button[aria-label="Next page"]',
    'button[aria-label="Go to next page"]',
    'a[aria-label="Next page"]',
    'button[aria-label*="next" i]',
    'a[aria-label*="next" i]',
    '[data-testid*="next" i]',
  ];

  // For URL collection: each job card is an <a> whose href already points
  // to the job's detail page -- we just read it, no clicking needed.
  const JOB_CARD_SELECTOR = 'a[href*="/jobs/"]';
  const JUNK_LINE_RE = /^(saved|share|quick apply|apply|apply externally|be an early applicant|ucsc collection)$/i;
  const PAY_LINE_RE = /^\$|^unpaid/i;

  function findNextButton() {
    for (const sel of NEXT_BUTTON_SELECTORS) {
      const el = document.querySelector(sel);
      if (el && !el.disabled && el.getAttribute("aria-disabled") !== "true") {
        return el;
      }
    }
    return null;
  }

  function extractCardInfo(anchor) {
    // The <a> itself is often an empty full-card overlay used just to make
    // the whole card clickable -- the real title/company text lives in
    // sibling elements. Read from the parent card container instead.
    const container =
      anchor.closest('[data-hook^="saved-job-card"]') || anchor.parentElement;
    const source = container && container.innerText ? container : anchor;
    const lines = source.innerText.split("\n").map((l) => l.trim()).filter(Boolean);

    // The pay line ("$20/hr", "Unpaid", etc.) is a reliable anchor point --
    // the line right before it is the job title, and the line before that
    // is the company, matching the site's consistent card layout.
    const payIndex = lines.findIndex((l) => PAY_LINE_RE.test(l));
    if (payIndex > 0) {
      const title = lines[payIndex - 1] || "";
      const company = payIndex > 1 ? lines[payIndex - 2] : "";
      return { title, company };
    }

    // Fallback: skip obviously-junk lines and take the first real one.
    const meaningful = lines.filter((l) => !JUNK_LINE_RE.test(l));
    return { title: meaningful[0] || "", company: "" };
  }

  function collectUrlsOnThisPage(urlList) {
    const cards = Array.from(document.querySelectorAll(JOB_CARD_SELECTOR)).filter(
      (el) => el.offsetParent !== null
    );
    for (const card of cards) {
      const { title, company } = extractCardInfo(card);
      if (title && card.href) {
        urlList.push({ listTitle: title, company, handshakeUrl: card.href });
      }
    }
  }

  const pages = [];
  const urls = [];
  let pageNum = 1;

  while (pageNum <= MAX_PAGES) {
    console.log(`Collecting page ${pageNum}...`);
    pages.push(document.body.innerText);
    collectUrlsOnThisPage(urls);

    const nextBtn = findNextButton();
    if (!nextBtn) {
      console.log(`No "next page" button found (or it's disabled) -- stopping after page ${pageNum}.`);
      break;
    }

    nextBtn.click();
    await new Promise((r) => setTimeout(r, PAGE_LOAD_DELAY_MS));
    pageNum++;
  }

  // -- Download the raw text file (for parser.py) --
  const combinedText = pages.join("\n\n");
  const textBlob = new Blob([combinedText], { type: "text/plain" });
  const textUrl = URL.createObjectURL(textBlob);
  const textLink = document.createElement("a");
  textLink.href = textUrl;
  textLink.download = "handshake_saved_jobs_raw.txt";
  document.body.appendChild(textLink);
  textLink.click();
  textLink.remove();
  URL.revokeObjectURL(textUrl);

  // -- Download the URLs file (for merge_urls.py) --
  const seen = new Set();
  const dedupedUrls = urls.filter((j) => {
    if (seen.has(j.handshakeUrl)) return false;
    seen.add(j.handshakeUrl);
    return true;
  });
  const jsonBlob = new Blob([JSON.stringify(dedupedUrls, null, 2)], { type: "application/json" });
  const jsonUrl = URL.createObjectURL(jsonBlob);
  const jsonLink = document.createElement("a");
  jsonLink.href = jsonUrl;
  jsonLink.download = "handshake_urls.json";
  document.body.appendChild(jsonLink);
  jsonLink.click();
  jsonLink.remove();
  URL.revokeObjectURL(jsonUrl);

  console.log(
    `Done. Collected ${pages.length} page(s) and ${dedupedUrls.length} unique job URL(s) -> ` +
    `handshake_saved_jobs_raw.txt and handshake_urls.json downloaded.`
  );
})();