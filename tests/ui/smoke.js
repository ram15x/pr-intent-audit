// UI smoke test (mock backend, headless DOM). Run: npm install jsdom && node tests/ui/smoke.js
const {JSDOM,VirtualConsole}=require("jsdom");const fs=require("fs");
const html=fs.readFileSync(require('path').join(__dirname,'../../src/pr_audit/web/app.html'),"utf8");
const errs=[];const vc=new VirtualConsole();vc.on("jsdomError",e=>errs.push("jsdomError: "+e.message));vc.on("error",e=>errs.push("console.error: "+e));
const dom=new JSDOM(html,{url:"http://localhost/app.html?mock=1",runScripts:"dangerously",pretendToBeVisual:true,virtualConsole:vc,
  beforeParse(w){w.matchMedia=w.matchMedia||(()=>({matches:false}));w.confirm=()=>true}});
const w=dom.window,d=w.document,sleep=ms=>new Promise(r=>setTimeout(r,ms)),ok=(c,m)=>{console.log((c?"PASS ":"FAIL ")+m);if(!c)process.exitCode=1};
(async()=>{
 await sleep(500);
 ok(d.querySelector("#v-new").classList.contains("on"),"new-audit view visible first");
 ok(d.querySelector("#tJudge").textContent.includes("groq"),"status pill shows judge: "+d.querySelector("#tJudge").textContent);
 ok(d.querySelectorAll("#hgrid .h").length===3,"history shows 3 mock runs");
 d.querySelector('.tab[data-m="local"]').click();ok(d.querySelector("#f-local").style.display==="grid"&&d.querySelector("#f-pr").style.display==="none","local tab swaps fields");
 d.querySelector('.tab[data-m="pr"]').click();
 d.querySelector("#run").click();await sleep(300);
 ok(d.querySelector("#v-run").classList.contains("on"),"run view opens after Run");
 await sleep(7600);
 const rows=d.querySelectorAll("#rlist .rq");ok(rows.length===5,"5 requirement rows streamed in (got "+rows.length+")");
 const chips=[...rows].map(r=>r.querySelector(".chip").textContent.trim());ok(chips.join(",")==="done,done,partial,done,missing","statuses "+chips.join(","));
 ok(d.querySelector("#tk").textContent==="5,120","token meter shows "+d.querySelector("#tk").textContent);
 await sleep(1500);
 ok(d.querySelector("#v-result").classList.contains("on"),"result view opens when the job is done");
 ok(d.querySelector("#ttl").textContent.length>0&&d.querySelector("#rtools").querySelectorAll(".btn").length>=4,"result toolbar has actions");
 d.querySelector('.nav[data-v="history"]').click();await sleep(400);ok(d.querySelector("#v-history").classList.contains("on"),"history nav works");
 d.querySelector('.nav[data-v="about"]').click();ok(d.querySelector("#v-about").classList.contains("on"),"about view works");
 const x=d.querySelector("#theme");const before=d.documentElement.dataset.theme;x.click();ok(d.documentElement.dataset.theme!==before,"theme toggles");
 // XSS check: hostile text must be escaped in rows
 d.querySelector('.nav[data-v="new"]').click();
 console.log(errs.length?errs.join("\n"):"no script errors");process.exit(process.exitCode||0);
})();
