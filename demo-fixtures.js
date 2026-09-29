(() => {
  const provenance = {
    evidence_present: true,
    evidence_schema: 2,
    authorization_status: "UNVERIFIED",
    video_identity_status: "UNVERIFIED",
    timeline_match_status: "VERIFIED",
    deep_links_allowed: false
  };

  const transcripts = {
    "demo-job-agentes": {
      job_id: "demo-job-agentes",
      result_kind: "TRANSCRIPT",
      transcript: {
        video_id: "demo-arquitetura-agentes",
        source: "demo_fixture",
        language: "pt-BR",
        provider: null,
        model: null,
        segments: [
          {id:"s1", text:"A memória durável fica fora do modelo para que o estado do sistema possa ser recuperado de forma verificável.", start_ms:12000, end_ms:20500},
          {id:"s2", text:"Um turno do agente pode envolver várias chamadas de modelo; o ciclo de vida pertence ao runtime, não ao LLM.", start_ms:20500, end_ms:31800},
          {id:"s3", text:"Provedores substituíveis ficam atrás de contratos pequenos, enquanto o domínio preserva conceitos estáveis.", start_ms:31800, end_ms:45200}
        ]
      },
      provenance
    },
    "demo-job-local": {
      job_id: "demo-job-local",
      result_kind: "TRANSCRIPT",
      transcript: {
        video_id: "demo-modelos-locais",
        source: "demo_fixture",
        language: "pt-BR",
        provider: null,
        model: null,
        segments: [
          {id:"s1", text:"Modelos locais podem funcionar como alternativa quando o adaptador de provedor continua explícito.", start_ms:5000, end_ms:13900},
          {id:"s2", text:"A escolha entre execução local e API deve considerar custo, latência, qualidade e disponibilidade.", start_ms:13900, end_ms:25100}
        ]
      },
      provenance
    }
  };

  const library = {
    result_kind: "LIBRARY",
    items: [
      {
        video_id: "demo-arquitetura-agentes",
        latest_job_id: "demo-job-agentes",
        version_count: 2,
        state: "COMPLETED",
        source: "demo_fixture",
        language: "pt-BR",
        provenance,
        artifacts: {transcript_present:true, sections_present:true, synthesis_present:true}
      },
      {
        video_id: "demo-modelos-locais",
        latest_job_id: "demo-job-local",
        version_count: 1,
        state: "COMPLETED",
        source: "demo_fixture",
        language: "pt-BR",
        provenance,
        artifacts: {transcript_present:true, sections_present:true, synthesis_present:false}
      }
    ],
    next_before: null
  };

  const sections = {
    "demo-job-agentes": {
      result_kind: "SECTIONS_ONLY",
      complete: true,
      planned_sections: 2,
      sections: [
        {
          index: 0,
          segment_ids: ["s1","s2"],
          analysis: {
            summary: "A primeira parte separa memória persistente, runtime e chamadas do modelo.",
            ideas: [
              {title:"Memória fora do LLM", explanation:"O estado recuperável não depende do contexto interno do modelo.", source_segment_ids:["s1"]},
              {title:"Turno diferente de chamada", explanation:"O runtime coordena múltiplas chamadas dentro de um mesmo turno.", source_segment_ids:["s2"]}
            ]
          }
        },
        {
          index: 1,
          segment_ids: ["s3"],
          analysis: {
            summary: "A segunda parte enfatiza contratos pequenos para manter provedores substituíveis.",
            ideas: [
              {title:"Adaptadores estreitos", explanation:"O domínio permanece estável enquanto integrações podem variar.", source_segment_ids:["s3"]}
            ]
          }
        }
      ]
    },
    "demo-job-local": {
      result_kind: "SECTIONS_ONLY",
      complete: true,
      planned_sections: 1,
      sections: [
        {
          index: 0,
          segment_ids: ["s1","s2"],
          analysis: {
            summary: "A transcrição compara execução local e APIs preservando um contrato comum de provedor.",
            ideas: [
              {title:"Trade-offs explícitos", explanation:"Custo, latência, qualidade e disponibilidade devem orientar a escolha.", source_segment_ids:["s2"]}
            ]
          }
        }
      ]
    }
  };

  const synthesis = {
    "demo-job-agentes": {
      result_kind: "GLOBAL_SYNTHESIS",
      analysis: {
        summary: "O conteúdo apresenta uma arquitetura de agentes que mantém estado, memória e lifecycle fora do modelo e usa adaptadores para evitar dependência rígida de provedores.",
        ideas: [
          {title:"Runtime como autoridade", explanation:"O runtime coordena estado e execução; o modelo participa como componente de raciocínio.", source_segment_ids:["s1","s2"]},
          {title:"Independência de provedor", explanation:"Contratos estreitos permitem trocar implementações sem contaminar o domínio.", source_segment_ids:["s3"]}
        ]
      },
      coverage: {
        total_segments: 3,
        referenced_segments: 3,
        beginning_referenced: true,
        middle_referenced: true,
        end_referenced: true
      }
    }
  };

  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), {status, headers: {"Content-Type":"application/json"}});

  window.fetch = async (input) => {
    const raw = typeof input === "string" ? input : input.url;
    const url = new URL(raw, window.location.href);
    const path = url.pathname;

    if (path.endsWith("/api/library/search")) {
      const q = (url.searchParams.get("q") || "").trim().toLocaleLowerCase("pt-BR");
      const items = [];
      for (const entry of library.items) {
        const transcript = transcripts[entry.latest_job_id];
        for (const segment of transcript.transcript.segments) {
          if (segment.text.toLocaleLowerCase("pt-BR").includes(q)) {
            items.push({video_id:entry.video_id, job_id:entry.latest_job_id, segment, provenance});
          }
        }
      }
      return json({result_kind:"TRANSCRIPT_SEARCH", query:q, items:items.slice(0,20), truncated:items.length>20});
    }

    if (path.endsWith("/api/library")) return json(library);

    const transcriptMatch = path.match(/\/api\/jobs\/([^/]+)\/transcript$/);
    if (transcriptMatch) {
      const value = transcripts[decodeURIComponent(transcriptMatch[1])];
      return value ? json(value) : json({detail:"JOB_NOT_FOUND"}, 404);
    }

    const sectionsMatch = path.match(/\/api\/jobs\/([^/]+)\/sections$/);
    if (sectionsMatch) {
      const value = sections[decodeURIComponent(sectionsMatch[1])];
      return value ? json(value) : json({detail:"JOB_NOT_FOUND"}, 404);
    }

    const synthesisMatch = path.match(/\/api\/jobs\/([^/]+)\/synthesis$/);
    if (synthesisMatch) {
      const value = synthesis[decodeURIComponent(synthesisMatch[1])];
      return value ? json(value) : json({detail:"SYNTHESIS_NOT_FOUND"}, 404);
    }

    return json({detail:"DEMO_ROUTE_NOT_FOUND"}, 404);
  };
})();