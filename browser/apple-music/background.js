/* Native messaging only. This extension has access to music.apple.com alone. */
let emberboxPort = null;
let chosenTab = null;

async function appleTab() {
  const tabs = await browser.tabs.query({url:'https://music.apple.com/*'});
  return tabs.find(tab => tab.id === chosenTab) || tabs.find(tab => tab.active) || tabs[0];
}
async function dispatch(request) {
  if (!request || !/^[a-f0-9]{32}$/.test(request.id || '') ||
      !['browse','tracks','play','status'].includes(request.method)) return;
  try {
    const tab = await appleTab();
    if (!tab) throw Error('Keep the signed-in Apple Music tab open.');
    const results = await browser.scripting.executeScript({
      target:{tabId:tab.id},world:'MAIN',func:emberboxAppleCommand,args:[request]
    });
    if (!results.length || results[0].error) throw Error('Could not access Apple Music. Reload its tab.');
    emberboxPort?.postMessage({id:request.id,result:results[0].result});
    browser.browserAction.setBadgeText({text:''});
  } catch (error) {
    // Never forward raw site exceptions, which may contain request headers.
    const known = ['Keep the signed-in','MusicKit is not ready','Sign in to Apple Music','This MusicKit version','Could not access'];
    const message = String(error?.message || '');
    emberboxPort?.postMessage({id:request.id,error:known.some(p=>message.startsWith(p)) ? message.slice(0,200) : 'Apple Music request failed. Check the signed-in tab and try again.'});
    browser.browserAction.setBadgeText({text:'!'});
  }
}
function connect() {
  if (emberboxPort) return;
  const port = browser.runtime.connectNative('org.emberbox.apple_music');
  emberboxPort = port;
  port.onMessage.addListener(dispatch);
  port.onDisconnect.addListener(() => {if (emberboxPort===port) emberboxPort=null;});
}
browser.browserAction.onClicked.addListener(async tab => {
  if (tab.url?.startsWith('https://music.apple.com/')) chosenTab=tab.id;
  connect();
});
setInterval(async()=>{if(!emberboxPort && await appleTab())connect();},4000);
connect();
