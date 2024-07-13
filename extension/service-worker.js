const chatPanel = "sidepanels/chat-panel.html";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "contextMenu1",
    title: "Chat",
    contexts: ["all"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "contextMenu1") {
    // open side panel
    chrome.sidePanel.setOptions({ path: chatPanel });
    chrome.sidePanel.open({ windowId: tab.windowId });

    // send context to side panel
    chrome.runtime.onConnect.addListener(async function (port) {
      if (port.name !== "chat") return;

      port.postMessage({ context: info.selectionText });

      return port;
    });
  }
});
