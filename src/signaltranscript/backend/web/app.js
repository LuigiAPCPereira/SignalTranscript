const ui={form:document.querySelector("#search-form"),input:document.querySelector("#search-input"),clear:document.querySelector("#clear-search"),list:document.querySelector("#library-list"),status:document.querySelector("#library-status"),loadMore:document.querySelector("#load-more"),readerEmpty:document.querySelector("#reader-empty"),reader:document.querySelector("#reader-content"),readerVideoId:document.querySelector("#reader-video-id"),readerMeta:document.querySelector("#reader-meta"),readerProvenance:document.querySelector("#reader-provenance"),readerStatus:document.querySelector("#reader-status"),segments:document.querySelector("#reader-segments"),knowledge:document.querySelector("#reader-knowledge"),tabs:[...document.querySelectorAll(".reader-tab")]};
const state={nextBefore:null,selectedJobId:null,transcript:null,currentView:"transcript"};

function el(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node}
function status(node,message,tone="neutral"){node.textContent=message;node.dataset.tone=tone}
async function requestJSON(path){const response=await fetch(path,{headers:{Accept:"application/json"}});if(!response.ok)throw new Error(`HTTP_${response.status}`);return response.json()}
function pill(label,available){const node=el("span","pill",available?label:`${label}: indisponível`);if(available)node.dataset.kind="available";return node}
function markCurrent(button,jobId){button.setAttribute("aria-current",String(jobId===state.selectedJobId))}
function formatTime(ms){if(!Number.isInteger(ms)||ms<0)return null;const total=Math.floor(ms/1000),hours=Math.floor(total/3600),minutes=Math.floor(total%3600/60),seconds=total%60;const prefix=hours>0?`${hours}:${String(minutes).padStart(2,"0")}`:String(minutes);return `${prefix}:${String(seconds).padStart(2,"0")}`}
function range(segment){const start=formatTime(segment.start_ms),end=formatTime(segment.end_ms);return start&&end?`${start}–${end}`:"Sem marca de tempo"}
function provenanceText(p){if(!p?.evidence_present)return"Proveniência não verificada. Timestamps são exibidos somente como informação textual.";if(p.video_identity_status!=="VERIFIED")return"A legenda possui evidência local, mas a identidade do vídeo ainda não foi verificada. Links temporais permanecem desabilitados.";if(!p.deep_links_allowed)return"A proveniência disponível ainda não autoriza links temporais.";return"Proveniência verificada para navegação temporal."}


function activateReaderView(view){
  state.currentView=view;
  for(const tab of ui.tabs)tab.setAttribute("aria-pressed",String(tab.dataset.view===view));
  ui.segments.hidden=view!=="transcript";
  ui.knowledge.hidden=view==="transcript";
}

function ideaList(ideas){
  const list=el("ul","idea-list");
  for(const idea of ideas||[]){
    const item=el("li");
    item.append(el("span","idea-title",idea.title));
    item.append(el("p","idea-explanation",idea.explanation));
    const refs=(idea.source_segment_ids||[]).join(", ");
    if(refs)item.append(el("div","evidence-refs",`Evidência: ${refs}`));
    list.append(item);
  }
  return list;
}

function renderSections(data){
  ui.knowledge.replaceChildren();
  ui.knowledge.append(el("p","knowledge-intro",data.complete
    ?"Análise por seções persistida. Estes resumos locais não constituem uma síntese global."
    :`Análise parcial: ${(data.sections||[]).length} de ${data.planned_sections} seções persistidas.`));
  if((data.sections||[]).length===0){
    ui.knowledge.append(el("p","knowledge-summary","Nenhuma seção analisada está persistida para este job."));
    return;
  }
  for(const section of data.sections){
    const block=el("section","knowledge-block");
    block.append(el("h3",null,`Seção ${section.index+1}`));
    block.append(el("p","knowledge-summary",section.analysis.summary));
    if((section.analysis.ideas||[]).length){
      block.append(ideaList(section.analysis.ideas));
    }
    const refs=(section.segment_ids||[]).join(", ");
    if(refs)block.append(el("div","evidence-refs",`Segmentos da seção: ${refs}`));
    ui.knowledge.append(block);
  }
}

function renderSynthesis(data){
  ui.knowledge.replaceChildren();
  ui.knowledge.append(el("p","knowledge-intro","Síntese global persistida. Ela resume o conteúdo da transcrição; não é verificação independente dos fatos."));
  const analysis=data.analysis||{};
  const block=el("section","knowledge-block");
  block.append(el("h3",null,"Resumo global"));
  block.append(el("p","knowledge-summary",analysis.summary||"Resumo indisponível."));
  if((analysis.ideas||[]).length)block.append(ideaList(analysis.ideas));
  ui.knowledge.append(block);
  const coverage=data.coverage;
  if(coverage){
    const coverageBlock=el("section","knowledge-block");
    coverageBlock.append(el("h3",null,"Cobertura de evidências"));
    const grid=el("div","coverage-grid");
    const values=[
      ["Segmentos totais",coverage.total_segments],
      ["Segmentos referenciados",coverage.referenced_segments],
      ["Início referenciado",coverage.beginning_referenced?"Sim":"Não"],
      ["Meio referenciado",coverage.middle_referenced?"Sim":"Não"],
      ["Fim referenciado",coverage.end_referenced?"Sim":"Não"],
    ];
    for(const [label,value] of values){
      const item=el("div","coverage-item");
      item.append(el("strong",null,label),document.createTextNode(String(value)));
      grid.append(item);
    }
    coverageBlock.append(grid);
    ui.knowledge.append(coverageBlock);
  }
}

async function openKnowledge(view){
  if(!state.selectedJobId)return;
  activateReaderView(view);
  ui.knowledge.replaceChildren();
  status(ui.readerStatus,view==="sections"?"Carregando análise por seções…":"Carregando síntese global…");
  const path=view==="sections"
    ?`/api/jobs/${encodeURIComponent(state.selectedJobId)}/sections`
    :`/api/jobs/${encodeURIComponent(state.selectedJobId)}/synthesis`;
  try{
    const data=await requestJSON(path);
    if(view==="sections"){
      if(data.result_kind!=="SECTIONS_ONLY")throw new Error("UNEXPECTED_RESULT_KIND");
      renderSections(data);
      status(ui.readerStatus,data.complete?"Análise por seções disponível localmente.":"Análise por seções parcialmente disponível.");
    }else{
      if(data.result_kind!=="GLOBAL_SYNTHESIS")throw new Error("UNEXPECTED_RESULT_KIND");
      renderSynthesis(data);
      status(ui.readerStatus,"Síntese global disponível localmente.");
    }
  }catch(error){
    ui.knowledge.replaceChildren();
    if(view==="synthesis"&&error.message==="HTTP_404"){
      ui.knowledge.append(el("p","knowledge-summary","Não há síntese global persistida para este item."));
      status(ui.readerStatus,"Síntese global não disponível.");
    }else{
      ui.knowledge.append(el("p","knowledge-summary",view==="sections"
        ?"Não foi possível abrir a análise por seções."
        :"Não foi possível abrir a síntese global."));
      status(ui.readerStatus,"Artefato de conhecimento indisponível.","error");
    }
  }
}

function libraryButton(item){const button=el("button","entry-button");button.type="button";button.dataset.jobId=item.latest_job_id;markCurrent(button,item.latest_job_id);button.append(el("span","entry-title",item.video_id),el("span","entry-meta",[item.language||"idioma não informado",item.source,`${item.version_count} ${item.version_count===1?"versão":"versões"}`].join(" · ")));const secondary=el("span","entry-secondary");secondary.append(pill("Transcrição",item.artifacts?.transcript_present===true),pill("Seções",item.artifacts?.sections_present===true),pill("Síntese",item.artifacts?.synthesis_present===true));button.append(secondary);button.addEventListener("click",()=>openTranscript(item.latest_job_id));return button}
function searchButton(hit){const button=el("button","entry-button");button.type="button";button.dataset.jobId=hit.job_id;markCurrent(button,hit.job_id);button.append(el("span","entry-title",hit.video_id),el("span","entry-snippet",hit.segment.text),el("span","entry-meta",range(hit.segment)));button.addEventListener("click",()=>openTranscript(hit.job_id));return button}
function render(items,factory,append=false){if(!append)ui.list.replaceChildren();const fragment=document.createDocumentFragment();for(const item of items){const li=el("li","library-item");li.append(factory(item));fragment.append(li)}ui.list.append(fragment)}
function loading(){ui.list.replaceChildren();const li=el("li");li.append(el("div","skeleton"));ui.list.append(li)}

async function loadLibrary({append=false}={}){ui.clear.hidden=true;if(!append){state.nextBefore=null;loading();status(ui.status,"Carregando biblioteca…")}try{const params=new URLSearchParams({limit:"20"});if(append&&state.nextBefore)params.set("before",String(state.nextBefore));const data=await requestJSON(`/api/library?${params}`);render(data.items||[],libraryButton,append);state.nextBefore=data.next_before??null;ui.loadMore.hidden=!state.nextBefore;if(!append&&(data.items||[]).length===0)status(ui.status,"Sua biblioteca está vazia. Importe uma transcrição para começar.");else status(ui.status,append?"Mais itens carregados.":`${(data.items||[]).length} itens visíveis.`)}catch{if(!append)ui.list.replaceChildren();ui.loadMore.hidden=true;status(ui.status,"Não foi possível carregar a biblioteca local.","error")}}
async function search(query){state.nextBefore=null;ui.loadMore.hidden=true;ui.clear.hidden=false;loading();status(ui.status,"Buscando nas transcrições atuais…");try{const params=new URLSearchParams({q:query,limit:"20"}),data=await requestJSON(`/api/library/search?${params}`),items=data.items||[];render(items,searchButton);if(items.length===0)status(ui.status,`Nenhuma ocorrência para “${query}”.`);else if(data.truncated)status(ui.status,`${items.length} ocorrências exibidas. Há mais resultados; refine a busca.`);else status(ui.status,`${items.length} ${items.length===1?"ocorrência":"ocorrências"}.`)}catch{ui.list.replaceChildren();status(ui.status,"A busca local falhou. Tente novamente.","error")}}

async function openTranscript(jobId){state.selectedJobId=jobId;state.transcript=null;activateReaderView("transcript");document.querySelectorAll(".entry-button").forEach(button=>markCurrent(button,button.dataset.jobId));ui.readerEmpty.hidden=true;ui.reader.hidden=false;ui.readerVideoId.textContent="Carregando…";ui.readerMeta.replaceChildren();ui.readerProvenance.textContent="";ui.segments.replaceChildren();ui.knowledge.replaceChildren();status(ui.readerStatus,"Carregando transcrição…");try{const data=await requestJSON(`/api/jobs/${encodeURIComponent(jobId)}/transcript`),transcript=data.transcript;state.transcript=transcript;ui.readerVideoId.textContent=transcript.video_id;ui.readerMeta.replaceChildren(el("span","pill",transcript.language||"idioma não informado"),el("span","pill",transcript.source),el("span","pill",`${transcript.segments.length} ${transcript.segments.length===1?"segmento":"segmentos"}`));ui.readerProvenance.textContent=provenanceText(data.provenance);const fragment=document.createDocumentFragment();for(const segment of transcript.segments){const li=el("li","segment");li.append(el("span","segment-time",range(segment)),el("p","segment-text",segment.text));fragment.append(li)}ui.segments.replaceChildren(fragment);status(ui.readerStatus,"Transcrição disponível localmente.")}catch{ui.readerVideoId.textContent="Transcrição indisponível";ui.segments.replaceChildren();status(ui.readerStatus,"Não foi possível abrir esta transcrição.","error")}}

ui.form.addEventListener("submit",event=>{event.preventDefault();const query=ui.input.value.trim();if(query.length<2){status(ui.status,"Digite pelo menos 2 caracteres para buscar.","error");ui.input.focus();return}search(query)});
ui.clear.addEventListener("click",()=>{ui.input.value="";loadLibrary();ui.input.focus()});
ui.loadMore.addEventListener("click",()=>loadLibrary({append:true}));
for(const tab of ui.tabs){
  tab.addEventListener("click",()=>{
    const view=tab.dataset.view;
    if(view==="transcript"){
      activateReaderView("transcript");
      status(ui.readerStatus,state.transcript?"Transcrição disponível localmente.":"Transcrição indisponível.");
      return;
    }
    openKnowledge(view);
  });
}
loadLibrary();
