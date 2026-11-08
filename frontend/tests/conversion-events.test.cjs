const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../assets/js/app.js'), 'utf8');
const account = fs.readFileSync(path.join(__dirname, '../assets/js/account.js'), 'utf8');
function functionSource(text, start, end) { return text.slice(text.indexOf(start), text.indexOf(end, text.indexOf(start))); }
test('a terminal username response emits once, while an interrupted stream emits no conversion', async () => {
  for (const complete of [true, false]) {
    const events = [];
    const lines = complete ? [{type:'complete', data:{partial:true, guest_access:{}}}, {type:'complete',data:{partial:true,guest_access:{}}}] : [{type:'progress'}];
    const body = new ReadableStream({start(controller) { controller.enqueue(new TextEncoder().encode(lines.map(x=>JSON.stringify(x)).join('\n'))); controller.close(); }});
    const context = { window:{MyReconAnalytics:{scanComplete:(...args)=>events.push(args)}}, CFG:{apiBase:'',endpoints:{usernameStream:'/stream'}},
      fetch:async()=>({ok:true,status:200,body}), TextDecoder, setScanning(){}, updateScanUI(){}, addLiveCard(){},
      rememberGuestReport(){},renderSafely(){},renderUsername(){},toast(){},pushHistory(){},bindActions(){} };
    vm.runInNewContext(functionSource(app,'  async function consumeUsernameStream(', '  // A scan from the account')+'\nglobalThis.run = consumeUsernameStream;',context);
    if(complete) { await context.run('fixture',{deep:false,scope:'standard'}); assert.deepEqual(events,[['username','quick',true]]); }
    else { await assert.rejects(context.run('fixture',{}),/did not complete/); assert.equal(events.length,0); }
  }
});
for (const isNewUser of [true,false]) {
  test(`popup authentication passes confirmed isNewUser=${isNewUser} to analytics`, async()=>{
    const observed=[];
    const context={devMode:false,enabled:true,auth:{},mod:{signInWithPopup:async()=>({user:{}}),getAdditionalUserInfo:()=>({isNewUser})},
      provider:()=>({}),hint(){},window:{MyReconAnalytics:{signUp:value=>observed.push(value)}}};
    vm.runInNewContext(functionSource(account,'  function signIn()','  async function signInRedirect()')+'\nglobalThis.run = signIn;',context);
    await context.run(); assert.deepEqual(observed,[isNewUser]);
  });
  test(`redirect authentication passes confirmed isNewUser=${isNewUser} to analytics`, async()=>{
    const observed=[];
    const mockAuth={getAuth:()=>({}),getRedirectResult:async()=>({user:{}}),getAdditionalUserInfo:()=>({isNewUser}),onAuthStateChanged:(_,callback)=>callback(null)};
    const context={enabled:true,devMode:false,loading:null,FB:{projectId:'fixture'},mockApp:{initializeApp:()=>({})},mockAuth,
      hint(){},emit(){},window:{MyReconAnalytics:{signUp:value=>observed.push(value)}},console};
    const code=functionSource(account,'  function load()','  async function token()')
      .replace('import(SDK + "firebase-app.js")','Promise.resolve(mockApp)')
      .replace('import(SDK + "firebase-auth.js")','Promise.resolve(mockAuth)');
    vm.runInNewContext(code+'\nglobalThis.run = load;',context);
    await context.run(); assert.deepEqual(observed,[isNewUser]);
  });
}
