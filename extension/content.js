function extractPageContent() {
  const body = document.querySelector("body");
  const divs = body.querySelectorAll("div");

  let pageContent = "";
  divs.forEach((div) => {
    pageContent += div.innerText + " ";
  });
  pageContent = pageContent.trim();

  const pageTitle = document.title;
  const pageURL = window.location.href;

  return {
    title: pageTitle,
    url: pageURL,
    content: pageContent,
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.pageContent) {
    console.assert(sender.tab === undefined);
    var content = extractPageContent();
    sendResponse({ content: content });
    return;
  }
});
