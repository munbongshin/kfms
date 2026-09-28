<template>
  <div class="help-view">
    <nav class="toc">
      <div class="toc-title">도움말</div>
      <a
        v-for="s in sections"
        :key="s.id"
        :href="`#${s.id}`"
        :class="{ active: current === s.id }"
        @click.prevent="jump(s.id)"
      >
        {{ s.title }}
      </a>
    </nav>

    <article ref="articleRef" class="doc" @scroll="onScroll">
      <!-- 1 -->
      <section id="overview">
        <h2>KFMS 소개</h2>
        <p>
          KFMS는 <strong>법인카드 데이터를 한국어 질문으로 조회</strong>하고,
          <strong>감사 기준에 어긋나는 의심 거래를 점검</strong>하는 프로그램입니다.
          SQL을 몰라도 "승인내역에서 가맹점별 승인금액 합계 상위 5건"처럼 물으면
          프로그램이 SQL을 만들어 실행하고 결과를 표와 차트로 보여 줍니다.
        </p>
        <div class="cards">
          <div class="card">
            <div class="card-h">질의</div>
            <p>한국어 질문 → SQL 생성 → 확인 후 실행</p>
          </div>
          <div class="card">
            <div class="card-h">데이터</div>
            <p>조회할 데이터베이스 연결, 엑셀 파일 올리기</p>
          </div>
          <div class="card">
            <div class="card-h">이력</div>
            <p>지난 질문 다시 보기·재실행·북마크</p>
          </div>
          <div class="card">
            <div class="card-h">점검</div>
            <p>고액·시간 외·주의 업종·분할결제 의심 거래 찾기</p>
          </div>
        </div>
      </section>

      <!-- 2 -->
      <section id="layout">
        <h2>화면 구성</h2>
        <div class="mock">
          <div class="mock-top">
            <span>KFMS</span>
            <span class="mock-tag">① 현재 연결 · 도움말</span>
          </div>
          <div class="mock-body">
            <div class="mock-side">
              <div class="mock-tabs">② 질의 · 데이터 · 이력 · 점검</div>
              <div class="mock-tree">
                ③ 테이블 트리<br />
                <span>연결 ▸ 테이블 ▸ 컬럼</span>
              </div>
              <div class="mock-fold">④ « 접기</div>
            </div>
            <div class="mock-main">⑤ 작업 영역<br /><span>선택한 기능의 화면</span></div>
          </div>
        </div>
        <table class="kv">
          <tbody>
            <tr><th>① 상단 바</th><td>지금 조회 중인 데이터베이스 연결 이름과 이 도움말 버튼이 있습니다.</td></tr>
            <tr><th>② 기능 탭</th><td>질의 · 데이터 · 이력 · 점검 네 화면을 오갑니다.</td></tr>
            <tr>
              <th>③ 테이블 트리</th>
              <td>
                연결을 펼치면 테이블이, 테이블을 펼치면 컬럼이 나옵니다. 컬럼은
                <strong>한글명</strong>(예: 카드번호) 옆에 실제 컬럼명(cardno)과 형식이 작게 표시됩니다.
                위 검색창에 한글명이나 컬럼명 어느 쪽을 넣어도 찾습니다.
              </td>
            </tr>
            <tr><th>④ 접기</th><td>왼쪽 영역을 좁혀 작업 영역을 넓힙니다. 설정은 다음에도 유지됩니다.</td></tr>
            <tr><th>⑤ 작업 영역</th><td>선택한 기능 화면이 표시됩니다.</td></tr>
          </tbody>
        </table>
      </section>

      <!-- 3 -->
      <section id="flow">
        <h2>동작 구조</h2>
        <p>질문 하나가 결과가 되기까지 다음 순서로 처리됩니다.</p>
        <ol class="flow">
          <li><b>질문 입력</b><span>한국어로 원하는 내용을 적습니다.</span></li>
          <li><b>SQL 생성</b><span>AI(LLM)가 테이블·컬럼의 한글명을 참고해 SQL을 만듭니다.</span></li>
          <li><b>안전성 검사</b><span>조회(SELECT)만 허용합니다. 데이터를 바꾸는 SQL은 차단됩니다.</span></li>
          <li><b>확인 후 실행</b><span>만들어진 SQL을 보고 실행 여부를 정합니다.</span></li>
          <li><b>결과 표시</b><span>표 · 차트 · SQL 탭으로 봅니다.</span></li>
          <li><b>이력 저장</b><span>질문과 SQL이 이력에 남아 다시 쓸 수 있습니다.</span></li>
        </ol>
        <div class="note">
          조회 전용으로 동작하므로 이 프로그램에서 원본 데이터가 바뀌거나 지워지지 않습니다.
        </div>
      </section>

      <!-- 3-1 -->
      <section id="architecture">
        <h2>SW 아키텍처</h2>
        <p>
          KFMS는 <strong>웹 화면(프론트엔드)</strong>, <strong>API 서버(백엔드)</strong>,
          <strong>AI 모델(LLM)</strong>, <strong>데이터베이스</strong> 네 부분으로 이루어진
          3계층 웹 애플리케이션입니다. 화면은 API 서버하고만 통신하며, 데이터베이스와 AI에는
          API 서버만 접근합니다.
        </p>

        <div class="arch">
          <div class="tier">
            <div class="tier-name">사용자</div>
            <div class="box">웹 브라우저</div>
          </div>
          <div class="link">HTTP</div>
          <div class="tier">
            <div class="tier-name">프론트엔드 <span>:5173</span></div>
            <div class="box primary">
              <b>Vue 3 SPA</b>
              <div class="chips">
                <span>화면 views</span><span>컴포넌트</span><span>상태 stores</span><span>API 클라이언트</span>
              </div>
            </div>
          </div>
          <div class="link">REST · JSON<br /><code>/api/v1</code></div>
          <div class="tier">
            <div class="tier-name">백엔드 <span>:8000</span></div>
            <div class="box primary">
              <b>FastAPI 서버</b>
              <div class="chips">
                <span>API 라우터</span><span>서비스</span><span>SQL 검증</span><span>점검 규칙</span><span>DB 접근</span>
              </div>
            </div>
          </div>
          <div class="link split">
            <span>SQL 생성 요청</span>
            <span>SQL 실행 · 저장</span>
          </div>
          <div class="tier two">
            <div>
              <div class="tier-name">AI (LLM)</div>
              <div class="box">
                <b>Ollama</b> <small>(기본, 사내 서버)</small><br />
                <b>Groq</b> <small>(선택, 외부 API)</small>
              </div>
            </div>
            <div>
              <div class="tier-name">데이터베이스 <span>:5434</span></div>
              <div class="box">
                <b>PostgreSQL 16</b> <small>(Docker)</small>
                <div class="dbs">
                  <div><b>kfms</b> 운영 정보</div>
                  <div><b>retail</b> 조회 대상</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <h3>기술 스택</h3>
        <table class="grid-table">
          <thead><tr><th>구분</th><th>기술</th><th>역할</th></tr></thead>
          <tbody>
            <tr><td>화면</td><td>Vue 3, TypeScript, Vite</td><td>단일 페이지 웹 애플리케이션</td></tr>
            <tr><td>UI</td><td>Element Plus, ECharts</td><td>표·입력 컴포넌트, 차트</td></tr>
            <tr><td>상태·통신</td><td>Pinia, Vue Router, Axios</td><td>화면 상태 보관, 화면 이동, API 호출</td></tr>
            <tr><td>API 서버</td><td>Python, FastAPI</td><td>REST API, 비동기 처리</td></tr>
            <tr><td>DB 접근</td><td>SQLAlchemy(async), asyncpg</td><td>연결 풀, 쿼리 실행</td></tr>
            <tr><td>SQL 검증</td><td>sqlparse</td><td>생성된 SQL의 안전성 검사</td></tr>
            <tr><td>AI</td><td>Ollama / Groq</td><td>한국어 질문 → SQL 변환</td></tr>
            <tr><td>데이터베이스</td><td>PostgreSQL 16 (Docker)</td><td>운영 정보 저장, 조회 대상 데이터</td></tr>
          </tbody>
        </table>

        <h3>프론트엔드 구성</h3>
        <table class="kv">
          <tbody>
            <tr><th>views</th><td>화면 단위 — 질의, 데이터, 이력, 점검, 도움말</td></tr>
            <tr><th>components</th><td>화면 조각 — 레이아웃(상단 바·기능 탭·테이블 트리), 질문 입력, SQL 확인 창, 결과 표·차트, 이력 목록, 연결 관리, 엑셀 올리기</td></tr>
            <tr><th>stores</th><td>화면 간에 공유하는 상태 — 연결·스키마(database), 질문·결과(query), 점검 결과(anomaly)</td></tr>
            <tr><th>services</th><td>API 서버 호출을 한곳에 모은 클라이언트(api.ts)</td></tr>
            <tr><th>utils</th><td>계산 결과 컬럼의 한글명 만들기 등 공통 기능</td></tr>
          </tbody>
        </table>

        <h3>백엔드 구성</h3>
        <p>요청은 위에서 아래 방향으로만 흐릅니다. 각 계층은 바로 아래 계층만 호출합니다.</p>
        <div class="layers">
          <div class="layer">
            <b>API 라우터</b>
            <span>databases · query · history · excel · anomaly — 요청 검사, 응답 형식</span>
          </div>
          <div class="layer">
            <b>서비스</b>
            <span>질의 처리(query), SQL 생성(llm), 테이블 보기(table_browser), 이상거래 점검(anomaly), 엑셀 적재(excel)</span>
          </div>
          <div class="layer side">
            <div><b>LLM 공급자</b><span>공통 규칙·프롬프트 + Ollama·Groq 구현</span></div>
            <div><b>점검 규칙</b><span>고액·시간 외·주의 업종·분할결제</span></div>
            <div><b>유틸</b><span>SQL 검증, 비밀번호 암호화</span></div>
          </div>
          <div class="layer">
            <b>데이터 접근</b>
            <span>연결 풀(조회 대상 DB), 저장소(repositories), 테이블 모델(models)</span>
          </div>
        </div>

        <h3>데이터 저장소</h3>
        <table class="grid-table">
          <thead><tr><th>DB</th><th>테이블</th><th>내용</th></tr></thead>
          <tbody>
            <tr><td rowspan="4"><b>kfms</b><br /><small>운영 정보</small></td><td><code>database_connections</code></td><td>조회 대상 DB 접속 정보 (비밀번호는 암호화 저장)</td></tr>
            <tr><td><code>query_history</code></td><td>질문·SQL·결과·북마크</td></tr>
            <tr><td><code>excel_uploads</code></td><td>올린 엑셀 파일과 만든 임시 테이블 목록</td></tr>
            <tr><td><code>anomaly_review</code></td><td>이상거래 검토 판정(확인함·정상)</td></tr>
            <tr><td rowspan="3"><b>retail</b><br /><small>조회 대상</small></td><td><code>card_data</code> + 뷰 5개</td><td>법인카드 데이터 (승인·매입·청구·카드정보·사용부서)</td></tr>
            <tr><td><code>retail_sales</code></td><td>소매 판매 예제 데이터</td></tr>
            <tr><td>엑셀 임시 테이블</td><td>엑셀 올리기로 만든 테이블</td></tr>
          </tbody>
        </table>
        <div class="note">
          운영 정보 DB(kfms)는 조회 대상으로 등록하지 않습니다. 다른 DB의 접속 정보가
          들어 있어, 질문으로 조회되면 안 되기 때문입니다.
        </div>

        <h3>Text-to-SQL 동작 원리</h3>
        <p>
          자연어 질문이 SQL이 되어 DBMS에서 실행되기까지, 화면 · API 서버 · LLM · DBMS가
          주고받는 내용을 번호 순서대로 나타냈습니다.
        </p>
        <figure class="t2s">
          <svg
            viewBox="0 0 980 560"
            role="img"
            aria-label="자연어 질문이 스키마 조회, 프롬프트 구성, LLM의 SQL 생성, 검증, 사용자 확인을 거쳐 DBMS에서 읽기 전용으로 실행되고 결과와 이력이 저장되는 흐름"
          >
            <defs>
              <marker id="t2s-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#1a5fa8" />
              </marker>
              <marker id="t2s-arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#98a2b3" />
              </marker>
            </defs>

            <!-- Lanes -->
            <g class="lane">
              <rect x="10" y="10" width="190" height="540" />
              <rect x="215" y="10" width="310" height="540" />
              <rect x="540" y="10" width="190" height="540" />
              <rect x="745" y="10" width="225" height="540" />
            </g>
            <g class="lane-head">
              <rect x="10" y="10" width="190" height="30" />
              <rect x="215" y="10" width="310" height="30" />
              <rect x="540" y="10" width="190" height="30" class="llm" />
              <rect x="745" y="10" width="225" height="30" class="db" />
              <text x="105" y="30">화면 (프론트엔드)</text>
              <text x="370" y="30">API 서버 (백엔드)</text>
              <text x="635" y="30">LLM</text>
              <text x="857" y="30">DBMS (PostgreSQL)</text>
            </g>

            <!-- Screen -->
            <g class="node">
              <rect x="25" y="66" width="160" height="64" />
              <text x="105" y="92" class="t">자연어 질문 입력</text>
              <text x="105" y="112" class="s">"카테고리별 총 매출액"</text>

              <rect x="25" y="262" width="160" height="64" />
              <text x="105" y="288" class="t">SQL 확인 창</text>
              <text x="105" y="308" class="s">생성된 SQL 검토</text>

              <rect x="25" y="460" width="160" height="64" />
              <text x="105" y="486" class="t">결과 표 · 차트</text>
              <text x="105" y="506" class="s">한글 머리글로 표시</text>
            </g>

            <!-- API server -->
            <g class="node">
              <rect x="240" y="66" width="240" height="64" />
              <text x="360" y="92" class="t">스키마 수집</text>
              <text x="360" y="112" class="s">테이블 · 컬럼 · 형식 · 한글명</text>

              <rect x="240" y="160" width="240" height="64" />
              <text x="360" y="186" class="t">프롬프트 구성</text>
              <text x="360" y="206" class="s">스키마 + 작성 규칙 + 질문</text>

              <rect x="240" y="262" width="240" height="64" />
              <text x="360" y="288" class="t">SQL 추출 · 검증</text>
              <text x="360" y="308" class="s">SELECT만 허용 · 최대 1,000행</text>

              <rect x="240" y="366" width="240" height="64" />
              <text x="360" y="392" class="t">SQL 실행</text>
              <text x="360" y="412" class="s">읽기 전용 세션</text>

              <rect x="240" y="460" width="240" height="64" />
              <text x="360" y="486" class="t">결과 정리 · 이력 저장</text>
              <text x="360" y="506" class="s">계산 컬럼에 한글명 부여</text>
            </g>

            <!-- LLM -->
            <g class="node llm">
              <rect x="555" y="160" width="160" height="150" />
              <text x="635" y="190" class="t">SQL 생성 모델</text>
              <text x="635" y="214" class="s">Ollama (사내 서버)</text>
              <text x="635" y="232" class="s">또는 Groq (외부 API)</text>
              <line x1="575" y1="250" x2="695" y2="250" />
              <text x="635" y="272" class="s">자연어 → SQL 변환</text>
              <text x="635" y="290" class="s">데이터 값은 받지 않음</text>
            </g>

            <!-- DBMS -->
            <g class="node db">
              <rect x="760" y="60" width="195" height="370" />
              <text x="857" y="86" class="t">retail · 조회 대상</text>
              <text x="857" y="108" class="s">card_data + 뷰 5개</text>
              <text x="857" y="126" class="s">retail_sales · 엑셀 테이블</text>
              <line x1="775" y1="146" x2="940" y2="146" />
              <text x="857" y="170" class="t sm">시스템 카탈로그</text>
              <text x="857" y="192" class="s">information_schema</text>
              <text x="857" y="210" class="s">테이블 · 컬럼 · 형식</text>
              <text x="857" y="236" class="s">COMMENT ON COLUMN</text>
              <text x="857" y="254" class="s">컬럼 한글명</text>
              <line x1="775" y1="276" x2="940" y2="276" />
              <text x="857" y="300" class="t sm">데이터</text>
              <text x="857" y="322" class="s">실제 거래 · 매출 행</text>
              <text x="857" y="352" class="s">read_only 세션에서만</text>
              <text x="857" y="370" class="s">조회 허용</text>

              <rect x="760" y="455" width="195" height="75" />
              <text x="857" y="481" class="t">kfms · 운영 정보</text>
              <text x="857" y="501" class="s">query_history (이력)</text>
              <text x="857" y="519" class="s">database_connections</text>
            </g>

            <!-- Internal steps in the API server -->
            <g class="flow-line">
              <line x1="360" y1="130" x2="360" y2="158" />
              <line x1="360" y1="224" x2="360" y2="260" />
              <line x1="360" y1="430" x2="360" y2="458" />
            </g>
            <g class="flow-line muted">
              <line x1="360" y1="326" x2="360" y2="364" />
            </g>
            <text x="368" y="350" class="note-t">Generate &amp; Execute는 바로 실행</text>

            <!-- Numbered exchanges -->
            <g class="flow-line">
              <!-- 1 question -->
              <line x1="185" y1="98" x2="238" y2="98" />
              <!-- 2 schema, both ways -->
              <line x1="482" y1="98" x2="758" y2="98" class="both" />
              <!-- 3 prompt -->
              <line x1="480" y1="186" x2="553" y2="186" />
              <!-- 4 SQL back -->
              <line x1="555" y1="294" x2="482" y2="294" />
              <!-- 5 SQL to screen -->
              <line x1="240" y1="294" x2="187" y2="294" />
              <!-- 6 approve -->
              <path d="M105 326 V398 H238" />
              <!-- 7 execute, both ways -->
              <line x1="482" y1="398" x2="758" y2="398" class="both" />
              <!-- 8 history -->
              <line x1="480" y1="492" x2="758" y2="492" />
              <!-- 9 result -->
              <line x1="240" y1="492" x2="187" y2="492" />
            </g>

            <g class="step">
              <text x="212" y="90">① 질문</text>
              <text x="620" y="90">② 스키마 · 한글명 조회</text>
              <text x="517" y="178">③ 프롬프트</text>
              <text x="517" y="286">④ SQL</text>
              <text x="213" y="286">⑤ SQL</text>
              <text x="113" y="360" class="start">⑥ 확인 후 실행</text>
              <text x="620" y="390">⑦ SQL 실행 · 결과 행</text>
              <text x="620" y="484">⑧ 질문·SQL 저장</text>
              <text x="213" y="484">⑨ 결과</text>
            </g>
          </svg>
          <figcaption>
            ① 질문 전송 → ② DBMS에서 테이블·컬럼 구조와 한글명(COMMENT)을 읽음 →
            ③ 스키마·규칙·질문으로 프롬프트를 만들어 LLM에 보냄 → ④ LLM이 SQL을 돌려줌
            (SELECT만 허용, 최대 1,000행으로 제한해 검증) → ⑤ 화면에 SQL 표시 →
            ⑥ 사용자가 확인하고 실행 → ⑦ DBMS에서 읽기 전용으로 실행 →
            ⑧ 이력 저장 → ⑨ 한글 머리글로 결과 표시
          </figcaption>
        </figure>

        <div class="note">
          LLM에는 <strong>스키마(테이블·컬럼 이름, 형식, 한글명)와 질문만</strong> 전달됩니다.
          실제 거래 데이터 값은 LLM으로 보내지 않고, SQL 실행은 항상 API 서버가
          DBMS에 직접 합니다.
        </div>

        <h3>예시로 보는 변환 과정</h3>
        <div class="t2s-example">
          <div class="ex narrow">
            <div class="ex-h">① 자연어 질문</div>
            <pre>카테고리별 총 매출액을 보여줘</pre>
          </div>
          <div class="ex-arrow">→</div>
          <div class="ex wide">
            <div class="ex-h">③ LLM에 보내는 프롬프트 <small>(발췌)</small></div>
            <pre>Table: retail_sales
Columns:
  - product_category (character varying) NULL -- 상품 카테고리
  - total_amount (numeric) NULL -- 매출액
  …
RULES:
1. Use ONLY SELECT statements …
6. Give every computed column … a short
   Korean alias in double quotes …
QUESTION: 카테고리별 총 매출액을 보여줘</pre>
          </div>
          <div class="ex-arrow">→</div>
          <div class="ex">
            <div class="ex-h">④ 생성된 SQL</div>
            <pre>SELECT product_category,
       SUM(total_amount) AS "총 매출액"
FROM retail_sales
GROUP BY product_category
LIMIT 1000</pre>
          </div>
          <div class="ex-arrow">→</div>
          <div class="ex">
            <div class="ex-h">⑨ 화면 결과</div>
            <table class="ex-table">
              <thead><tr><th>상품 카테고리</th><th>총 매출액</th></tr></thead>
              <tbody>
                <tr><td>Electronics</td><td>156,905</td></tr>
                <tr><td>Clothing</td><td>155,580</td></tr>
                <tr><td>Beauty</td><td>143,515</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <p class="sub">
          한글명(COMMENT)이 프롬프트에 들어가 있어 LLM이 "카테고리", "매출액" 같은 우리말을
          실제 컬럼(<code>product_category</code>, <code>total_amount</code>)에 연결할 수 있습니다.
        </p>

        <h3>이상거래 점검 흐름</h3>
        <table class="grid-table seq">
          <thead><tr><th>#</th><th>어디서</th><th>무엇을</th></tr></thead>
          <tbody>
            <tr><td>1</td><td>화면 → API</td><td><code>GET /anomaly/findings</code>로 대상·기간·규칙 전송</td></tr>
            <tr><td>2</td><td>서비스 → DB</td><td>대상 뷰(승인·매입·청구)에서 기간 내 거래를 읽음</td></tr>
            <tr><td>3</td><td>점검 규칙</td><td>규칙별로 의심 거래를 찾아 점검 결과 생성 (AI를 쓰지 않는 규칙 기반)</td></tr>
            <tr><td>4</td><td>서비스 → kfms</td><td>저장된 검토 판정을 붙이고, 판정 뒤 거래가 바뀐 건은 "검토 후 변경됨" 표시</td></tr>
            <tr><td>5</td><td>화면 → API</td><td>펼치면 <code>/findings/transactions</code>로 상세 거래, 판정 시 <code>/findings/review</code>로 저장</td></tr>
          </tbody>
        </table>

        <h3>보안·안전 설계</h3>
        <ul>
          <li><strong>이중 읽기 전용</strong> — SQL 검증기가 SELECT 외 명령을 막고, DB 세션 자체도 읽기 전용(<code>default_transaction_read_only</code>)으로 엽니다.</li>
          <li><strong>결과 제한</strong> — 한 번에 최대 1,000행까지만 돌려줍니다.</li>
          <li><strong>이름 검증</strong> — 테이블 바로 보기의 테이블·컬럼 이름은 실제 스키마에 있는지 확인한 뒤에만 SQL에 넣습니다.</li>
          <li><strong>접속 정보 암호화</strong> — 조회 대상 DB의 비밀번호는 암호화(Fernet)해 저장합니다.</li>
          <li><strong>DB 분리</strong> — 운영 정보(kfms)와 조회 대상(retail)을 서로 다른 DB로 나눕니다.</li>
        </ul>
      </section>

      <!-- 4 -->
      <section id="data">
        <h2>데이터 구성</h2>
        <p>
          법인카드 원천 데이터는 <code>card_data</code> 한 테이블에 모여 있고, 용도별로
          나눠 보는 <strong>뷰</strong>가 있습니다. 질문할 때는 뷰 이름 대신
          "승인내역에서", "매입내역에서"처럼 우리말로 대상을 밝혀 주면 정확해집니다.
        </p>
        <table class="grid-table">
          <thead><tr><th>이름</th><th>내용</th></tr></thead>
          <tbody>
            <tr><td><code>v_approval</code></td><td>승인내역 — 카드 승인 시점의 거래</td></tr>
            <tr><td><code>v_acquire</code></td><td>매입내역 — 가맹점이 매입 청구한 거래</td></tr>
            <tr><td><code>v_bill</code></td><td>청구내역 — 결제일에 청구된 금액</td></tr>
            <tr><td><code>v_card_info</code></td><td>카드정보 — 카드별 발급·회원 정보</td></tr>
            <tr><td><code>v_card_dept</code></td><td>법인카드 사용부서 정보</td></tr>
            <tr><td><code>card_data</code></td><td>위 다섯 가지를 합친 통합 테이블 (원천 테이블명 컬럼으로 구분)</td></tr>
          </tbody>
        </table>
        <h3>컬럼 이름 표시</h3>
        <p>
          결과 표의 머리글은 <strong>한글명</strong>을 크게, 실제 컬럼명을 작게 보여 줍니다.
          두 컬럼이 같은 한글명을 쓰는 경우(예: 사업자번호)가 있어 컬럼명도 함께 표시합니다.
          머리글에 마우스를 올리면 정의서의 전체 이름을 볼 수 있습니다.
        </p>
        <p>
          합계·건수 같은 계산 결과는 "승인금액 합계", "건수"처럼 한글로 표시됩니다.
        </p>
      </section>

      <!-- 5 -->
      <section id="query">
        <h2>질의 사용법</h2>
        <ol class="steps">
          <li>왼쪽 트리에서 <strong>연결</strong>(예: Retail Sales DB)을 누릅니다. 상단 바에 연결 이름이 표시됩니다.</li>
          <li>질문 칸에 한국어로 질문을 적습니다.</li>
          <li>
            버튼을 누릅니다.
            <table class="kv inner">
              <tbody>
                <tr><th>Generate SQL</th><td>SQL만 만들어 확인 창에 보여 줍니다. 내용을 보고 <em>Execute Query</em>로 실행합니다.</td></tr>
                <tr><th>Generate &amp; Execute</th><td>SQL을 만들어 바로 실행합니다.</td></tr>
                <tr><th>Clear</th><td>질문과 결과를 지웁니다.</td></tr>
              </tbody>
            </table>
          </li>
          <li>결과는 <strong>표</strong>, <strong>차트</strong>, <strong>SQL</strong> 탭에서 봅니다. 오른쪽 <em>CSV</em> 버튼으로 파일로 저장합니다.</li>
        </ol>

        <h3>자주 쓰는 질문</h3>
        <p>
          이력에서 ★ 표시한 질문이 질의 화면의 "자주 쓰는 질문"에 버튼으로 나옵니다.
          누르면 AI를 거치지 않고 저장된 SQL을 바로 실행하므로 빠르고 결과가 항상 같습니다.
        </p>

        <h3>테이블 바로 보기</h3>
        <ul>
          <li>트리에서 테이블 이름을 <strong>더블클릭</strong>하면 테이블 내용이 표로 열립니다.</li>
          <li>아래 페이지 이동으로 전체 행을 볼 수 있고, 한 페이지 행 수(50~500)를 바꿀 수 있습니다.</li>
          <li>표 위 <em>전체 컬럼</em> 칸에서 보고 싶은 컬럼만 고릅니다. 한글명으로 검색되고, <em>전체 보기</em>로 되돌립니다.</li>
          <li>머리글의 ▲▼를 누르면 테이블 전체 기준으로 정렬됩니다.</li>
          <li>트리에서 컬럼을 한 번 누르면 질문 칸에 그 컬럼명이 들어갑니다.</li>
        </ul>

        <h3>질문을 잘 쓰는 요령</h3>
        <ul>
          <li>대상을 밝히세요: "<em>승인내역에서</em> 가맹점별 승인금액 합계"</li>
          <li>기간을 적으세요: "2023년 6월 승인내역 중 …"</li>
          <li>개수를 정하세요: "… 상위 5건"</li>
          <li>결과가 이상하면 <strong>SQL 탭</strong>에서 조건을 확인하고 질문을 고쳐 다시 물어보세요.</li>
        </ul>
      </section>

      <!-- 6 -->
      <section id="databases">
        <h2>데이터 (연결 관리)</h2>
        <h3>데이터베이스 연결</h3>
        <ul>
          <li><em>Add Connection</em>으로 이름·호스트·포트·DB 이름·계정을 입력해 연결을 추가합니다.</li>
          <li><strong>Read-Only(읽기 전용)</strong>를 켜 두기를 권장합니다.</li>
          <li><em>Test</em>로 연결이 되는지 확인하고, 필요 없는 연결은 삭제합니다.</li>
          <li>Active가 켜진 연결만 왼쪽 트리에 나타납니다.</li>
        </ul>
        <h3>엑셀 파일 올리기</h3>
        <ul>
          <li>엑셀 파일을 올리면 임시 테이블로 만들어져 질문 대상이 됩니다.</li>
          <li>
            임시 테이블은 올린 뒤 <strong>24시간이 지나면 만료</strong>됩니다. 목록의 Expires에서
            만료 시각을 확인하세요. 만료된 테이블을 지우는 작업은 아직 자동으로 돌지 않으니,
            다 쓴 파일은 목록에서 직접 삭제하세요.
          </li>
        </ul>
      </section>

      <!-- 7 -->
      <section id="history">
        <h2>이력</h2>
        <ul>
          <li>실행한 질문과 SQL, 결과 행 수, 소요 시간이 최신순으로 쌓입니다. 상태로 걸러 볼 수 있습니다.</li>
          <li>행을 누르면 질문·SQL·오류 내용 등 상세 정보를 봅니다.</li>
          <li><em>Re-run</em>으로 저장된 SQL을 다시 실행합니다.</li>
          <li><strong>★</strong>를 누르면 북마크되어 질의 화면의 "자주 쓰는 질문"에 추가됩니다.</li>
          <li>
            <strong>전체 삭제</strong>는 북마크(★)한 이력은 남기고 나머지를 모두 지웁니다.
            <span class="warn">되돌릴 수 없으니 남길 이력은 먼저 ★ 해 두세요.</span>
          </li>
        </ul>
      </section>

      <!-- 8 -->
      <section id="anomaly">
        <h2>이상거래 점검</h2>
        <p>선택한 대상과 기간에서 감사 기준 위반이 의심되는 거래를 찾아 목록으로 보여 줍니다.</p>

        <h3>조회 조건</h3>
        <table class="kv">
          <tbody>
            <tr><th>점검대상</th><td>승인내역 · 매입내역 · 청구내역 중 하나, 또는 <em>전체</em>. 괄호 안은 대상 건수입니다.</td></tr>
            <tr><th>규칙</th><td>특정 규칙만 볼 때 고릅니다. 비워 두면 모든 규칙을 적용합니다.</td></tr>
            <tr><th>조회기간</th><td>시작일 ~ 종료일. 한쪽만 넣어도 됩니다. 전체·1개월·3개월·6개월 버튼으로 빠르게 정할 수 있습니다.</td></tr>
            <tr><th>검토상태</th><td>미검토 · 확인함 · 정상 중 골라 봅니다.</td></tr>
          </tbody>
        </table>

        <h3>점검 규칙</h3>
        <table class="grid-table">
          <thead><tr><th>규칙</th><th>심각도</th><th>찾는 거래</th></tr></thead>
          <tbody>
            <tr><td>고액 결제</td><td><span class="sev high">높음</span></td><td>한 건 금액이 <strong>50만원 이상</strong></td></tr>
            <tr><td>시간 외 사용</td><td><span class="sev medium">보통</span></td><td><strong>주말</strong>(토·일) 또는 <strong>심야</strong>(23시 ~ 다음날 06시) 결제</td></tr>
            <tr><td>주의 업종</td><td><span class="sev high">높음</span></td><td>상품권 전문판매, 볼링장, 영화관, 화원, 기타회원제형태업소, 자사카드발행백화점</td></tr>
            <tr><td>분할결제 의심</td><td><span class="sev medium">보통</span></td><td>같은 카드로 <strong>같은 가맹점에서 같은 날 2건 이상</strong> 결제 (한도 회피 의심)</td></tr>
          </tbody>
        </table>
        <div class="note">
          청구내역에는 시간·가맹점·업종 정보가 없어 <strong>고액 결제</strong> 규칙만 적용됩니다.
          적용할 수 없는 규칙은 규칙 목록에 흐리게 표시됩니다.
        </div>

        <h3>결과 검토</h3>
        <ol class="steps">
          <li>행 왼쪽 ▸를 눌러 펼치면 해당 거래의 상세 내역이 나옵니다. 카드번호는 감사 확인을 위해 전체 번호로 표시됩니다.</li>
          <li><em>전체 보기</em>로 거래의 모든 항목을 볼 수 있습니다.</li>
          <li>
            검토 결과를 표시합니다. <strong>확인</strong>은 문제로 확인한 건,
            <strong>정상</strong>은 문제가 없는 건입니다. 판정은 저장되어 다음 조회에도 보입니다.
          </li>
          <li>
            검토한 뒤 거래 내용이 바뀌면 "<span class="stale">검토 후 변경됨</span>"이 표시되고
            다시 판정할 수 있게 됩니다.
          </li>
          <li>오른쪽 위 <strong>파일저장</strong>으로 조회 결과를 파일로 내려받습니다.</li>
        </ol>
      </section>

      <!-- 9 -->
      <section id="faq">
        <h2>문제 해결</h2>
        <dl class="faq">
          <dt>버튼이 눌리지 않아요.</dt>
          <dd>왼쪽 트리에서 연결을 먼저 선택하세요. 연결이 선택되지 않으면 질문·점검 버튼이 꺼져 있습니다.</dd>

          <dt>트리에 "스키마를 불러올 수 없습니다"가 나와요.</dt>
          <dd>
            데이터베이스 서버가 멈췄을 수 있습니다. 서버(도커의 <code>kfms-postgres</code>)가
            실행 중인지 확인한 뒤 그 문구를 눌러 다시 불러오세요.
          </dd>

          <dt>결과가 질문과 달라요.</dt>
          <dd>
            SQL 탭에서 어떤 테이블·조건으로 조회했는지 확인하세요. 대상(승인내역 등)과
            기간을 질문에 분명히 적으면 대부분 해결됩니다.
          </dd>

          <dt>"SQL Blocked"가 나와요.</dt>
          <dd>데이터를 바꾸는 SQL이 만들어져 차단된 것입니다. 조회하는 질문으로 바꿔 다시 물어보세요.</dd>

          <dt>머리글이 영어로 나와요.</dt>
          <dd>
            계산 방식이 복잡한 컬럼은 한글명을 정할 수 없어 SQL에 적힌 이름이 그대로 나옵니다.
            질문을 다시 실행하면 대부분 한글 이름으로 만들어집니다.
          </dd>
        </dl>
      </section>
    </article>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const sections = [
  { id: 'overview', title: 'KFMS 소개' },
  { id: 'layout', title: '화면 구성' },
  { id: 'flow', title: '동작 구조' },
  { id: 'architecture', title: 'SW 아키텍처' },
  { id: 'data', title: '데이터 구성' },
  { id: 'query', title: '질의 사용법' },
  { id: 'databases', title: '데이터 (연결 관리)' },
  { id: 'history', title: '이력' },
  { id: 'anomaly', title: '이상거래 점검' },
  { id: 'faq', title: '문제 해결' },
]

const route = useRoute()
const router = useRouter()
const articleRef = ref<HTMLElement>()
const current = ref(sections[0].id)

function jump(id: string) {
  const el = articleRef.value?.querySelector<HTMLElement>(`#${id}`)
  if (!el || !articleRef.value) return
  articleRef.value.scrollTo({ top: el.offsetTop - 12, behavior: 'smooth' })
  current.value = id
  // Keep the section in the URL so a help link can point straight at it.
  router.replace({ hash: `#${id}` })
}

/** Highlight the section whose heading has scrolled past the top. */
function onScroll() {
  const article = articleRef.value
  if (!article) return
  // The last section is too short to reach the top; at the bottom, it is the one.
  if (article.scrollTop + article.clientHeight >= article.scrollHeight - 4) {
    current.value = sections[sections.length - 1].id
    return
  }
  const top = article.scrollTop + 40
  let active = sections[0].id
  for (const s of sections) {
    const el = article.querySelector<HTMLElement>(`#${s.id}`)
    if (el && el.offsetTop <= top) active = s.id
  }
  current.value = active
}

onMounted(async () => {
  await nextTick()
  const id = route.hash.slice(1)
  if (sections.some((s) => s.id === id)) jump(id)
})
</script>

<style scoped>
.help-view {
  display: flex;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.toc {
  display: flex;
  flex-direction: column;
  width: 180px;
  flex-shrink: 0;
  padding: 10px 0;
  background: #fff;
  border: 1px solid #d3dae3;
  align-self: flex-start;
}

.toc-title {
  padding: 4px 14px 10px;
  font-weight: 700;
  color: #1b3c74;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 6px;
}

.toc a {
  padding: 6px 14px;
  font-size: 13px;
  color: #475467;
  text-decoration: none;
  border-left: 3px solid transparent;
}

.toc a:hover {
  background: #f4f6f9;
  color: #1a5fa8;
}

.toc a.active {
  border-left-color: #1a5fa8;
  color: #1a5fa8;
  font-weight: 600;
  background: #eef3fa;
}

.doc {
  /* Makes section offsetTop relative to this scroller, which jump() relies on. */
  position: relative;
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 8px 28px 60px;
  background: #fff;
  border: 1px solid #d3dae3;
  font-size: 14px;
  line-height: 1.7;
  color: #1f2937;
}

section {
  padding: 18px 0 26px;
  border-bottom: 1px solid #edf0f4;
}

section:last-child {
  border-bottom: none;
}

h2 {
  margin: 0 0 12px;
  padding-left: 10px;
  border-left: 4px solid #1b3c74;
  font-size: 19px;
  color: #1b3c74;
}

h3 {
  margin: 20px 0 8px;
  font-size: 15px;
  color: #1f3a66;
}

p {
  margin: 0 0 10px;
}

ul,
ol {
  margin: 0 0 10px;
  padding-left: 22px;
}

li {
  margin: 4px 0;
}

code {
  padding: 1px 5px;
  background: #f1f4f8;
  border: 1px solid #e1e6ed;
  border-radius: 3px;
  font-size: 12.5px;
}

em {
  font-style: normal;
  font-weight: 600;
  color: #1a5fa8;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.card {
  padding: 12px 14px;
  border: 1px solid #d3dae3;
  border-top: 3px solid #1a5fa8;
  background: #f9fbfd;
}

.card-h {
  font-weight: 700;
  color: #1b3c74;
  margin-bottom: 4px;
}

.card p {
  margin: 0;
  font-size: 13px;
  color: #475467;
}

/* Screen-layout sketch */
.mock {
  max-width: 620px;
  margin: 6px 0 14px;
  border: 1px solid #b8c3d3;
  font-size: 12px;
}

.mock-top {
  display: flex;
  justify-content: space-between;
  padding: 7px 10px;
  background: #1b3c74;
  color: #fff;
  font-weight: 700;
}

.mock-tag {
  font-weight: 400;
  opacity: 0.9;
}

.mock-body {
  display: flex;
  height: 170px;
}

.mock-side {
  display: flex;
  flex-direction: column;
  width: 34%;
  background: #f7f8fa;
  border-right: 1px solid #d3dae3;
}

.mock-tabs {
  padding: 7px 8px;
  border-bottom: 1px solid #d3dae3;
  color: #1a5fa8;
  font-weight: 600;
}

.mock-tree {
  flex: 1;
  padding: 8px;
  color: #344054;
}

.mock-tree span,
.mock-main span {
  color: #8a94a3;
}

.mock-fold {
  padding: 4px 8px;
  border-top: 1px solid #d3dae3;
  background: #eef1f5;
  color: #8a94a3;
}

.mock-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f4f6f9;
  color: #344054;
  text-align: center;
}

.kv {
  width: 100%;
  border-collapse: collapse;
  margin: 6px 0 10px;
  font-size: 13px;
}

.kv th,
.kv td {
  padding: 7px 10px;
  border: 1px solid #e1e6ed;
  vertical-align: top;
  text-align: left;
}

.kv th {
  width: 140px;
  background: #f4f6f9;
  color: #1f3a66;
  font-weight: 600;
  white-space: nowrap;
}

.kv.inner {
  margin-top: 6px;
}

.grid-table {
  width: 100%;
  border-collapse: collapse;
  margin: 6px 0 10px;
  font-size: 13px;
}

.grid-table th {
  padding: 7px 10px;
  background: #1b3c74;
  color: #fff;
  text-align: left;
  font-weight: 600;
}

.grid-table td {
  padding: 7px 10px;
  border-bottom: 1px solid #e1e6ed;
}

.grid-table tbody tr:nth-child(even) {
  background: #f9fbfd;
}

.flow {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  padding: 0;
  counter-reset: step;
}

.flow li {
  position: relative;
  margin: 0;
  padding: 10px 12px 10px 38px;
  border: 1px solid #d3dae3;
  background: #f9fbfd;
  counter-increment: step;
}

.flow li::before {
  content: counter(step);
  position: absolute;
  left: 10px;
  top: 10px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #1a5fa8;
  color: #fff;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}

.flow b {
  display: block;
  color: #1b3c74;
}

.flow span {
  font-size: 12.5px;
  color: #475467;
}

/* Text-to-SQL diagram */
.t2s {
  margin: 8px 0 12px;
  padding: 12px;
  border: 1px solid #d3dae3;
  background: #fff;
}

.t2s svg {
  display: block;
  width: 100%;
  max-width: 980px;
  height: auto;
  font-family: inherit;
}

.t2s .lane rect {
  fill: #f7f9fc;
  stroke: #d3dae3;
}

.t2s .lane-head rect {
  fill: #1b3c74;
}

.t2s .lane-head rect.llm {
  fill: #8a5a00;
}

.t2s .lane-head rect.db {
  fill: #23613f;
}

.t2s .lane-head text {
  fill: #fff;
  font-size: 13px;
  font-weight: 700;
  text-anchor: middle;
}

.t2s .node rect {
  fill: #fff;
  stroke: #1a5fa8;
  stroke-width: 1.2;
}

.t2s .node.llm rect {
  fill: #fff8eb;
  stroke: #b7791f;
}

.t2s .node.db rect {
  fill: #f0f8f3;
  stroke: #2f855a;
}

.t2s .node line {
  stroke: #cbd5e1;
}

.t2s .node text {
  text-anchor: middle;
}

.t2s .t {
  font-size: 13.5px;
  font-weight: 700;
  fill: #1b3c74;
}

.t2s .t.sm {
  font-size: 12.5px;
}

.t2s .node.llm .t {
  fill: #7a4a00;
}

.t2s .node.db .t {
  fill: #1f5135;
}

.t2s .s {
  font-size: 11.5px;
  fill: #475467;
}

.t2s .flow-line line,
.t2s .flow-line path {
  fill: none;
  stroke: #1a5fa8;
  stroke-width: 1.6;
  marker-end: url(#t2s-arrow);
}

.t2s .flow-line line.both {
  marker-start: url(#t2s-arrow);
}

.t2s .flow-line.muted line {
  stroke: #98a2b3;
  stroke-dasharray: 4 3;
  marker-end: url(#t2s-arrow-muted);
}

.t2s .note-t {
  font-size: 10.5px;
  fill: #8a94a3;
}

.t2s .step text {
  font-size: 11.5px;
  font-weight: 700;
  fill: #1a5fa8;
  text-anchor: middle;
  paint-order: stroke;
  stroke: #f7f9fc;
  stroke-width: 4px;
}

.t2s .step text.start {
  text-anchor: start;
}

.t2s figcaption {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #edf0f4;
  font-size: 12.5px;
  line-height: 1.7;
  color: #475467;
}

.t2s-example {
  display: flex;
  align-items: stretch;
  gap: 6px;
  margin: 6px 0 8px;
}

.ex {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #d3dae3;
  background: #f9fbfd;
}

/* The prompt is the longest text; the question is one line. */
.ex.wide {
  flex: 2;
}

.ex.narrow {
  flex: 0.7;
}

.ex-h {
  padding: 6px 10px;
  background: #eef3fa;
  border-bottom: 1px solid #d3dae3;
  font-size: 12.5px;
  font-weight: 700;
  color: #1b3c74;
}

.ex-h small {
  font-weight: 400;
  color: #6b7686;
}

.ex pre {
  flex: 1;
  margin: 0;
  padding: 8px 10px;
  overflow-x: auto;
  font-size: 11.5px;
  line-height: 1.55;
  white-space: pre;
}

.ex-arrow {
  align-self: center;
  color: #1a5fa8;
  font-weight: 700;
}

.ex-table {
  margin: 8px 10px;
  border-collapse: collapse;
  font-size: 12px;
}

.ex-table th {
  padding: 4px 8px;
  background: #f4f6f9;
  border: 1px solid #e1e6ed;
  color: #1f3a66;
}

.ex-table td {
  padding: 4px 8px;
  border: 1px solid #e1e6ed;
}

.ex-table td:last-child {
  text-align: right;
}

.sub {
  font-size: 13px;
  color: #475467;
}

/* Architecture diagram */
.arch {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  max-width: 720px;
  margin: 8px 0 16px;
}

.tier-name {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #1f3a66;
}

.tier-name span {
  font-weight: 400;
  color: #8a94a3;
}

.tier.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.box {
  padding: 10px 12px;
  border: 1px solid #b8c3d3;
  background: #f9fbfd;
  font-size: 13px;
}

.box.primary {
  border-color: #1a5fa8;
  background: #eef3fa;
}

.box small {
  color: #6b7686;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}

.chips span {
  padding: 1px 8px;
  background: #fff;
  border: 1px solid #c9d5e6;
  border-radius: 10px;
  font-size: 12px;
  color: #344054;
}

.dbs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 6px;
}

.dbs div {
  padding: 5px 8px;
  background: #fff;
  border: 1px dashed #b8c3d3;
  font-size: 12px;
}

/* Connector between tiers: a short vertical line with its protocol. */
.link {
  position: relative;
  padding: 6px 0 6px 26px;
  margin-left: 24px;
  border-left: 2px solid #1a5fa8;
  font-size: 11.5px;
  line-height: 1.4;
  color: #6b7686;
}

.link::after {
  content: '';
  position: absolute;
  left: -6px;
  bottom: -1px;
  border: 5px solid transparent;
  border-top-color: #1a5fa8;
}

.link.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-left: 0;
  padding-left: 0;
  border-left: none;
}

.link.split span {
  position: relative;
  margin-left: 24px;
  padding: 6px 0 6px 26px;
  border-left: 2px solid #1a5fa8;
}

.link.split::after {
  display: none;
}

.link.split span::after {
  content: '';
  position: absolute;
  left: -6px;
  bottom: -1px;
  border: 5px solid transparent;
  border-top-color: #1a5fa8;
}

.layers {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 720px;
  margin: 6px 0 12px;
}

.layer {
  display: flex;
  gap: 12px;
  align-items: baseline;
  padding: 9px 12px;
  border: 1px solid #c9d5e6;
  background: #f9fbfd;
  font-size: 13px;
}

.layer b {
  flex-shrink: 0;
  width: 90px;
  color: #1b3c74;
}

.layer span {
  color: #475467;
}

.layer.side {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 0;
  border: none;
  background: none;
}

.layer.side div {
  display: flex;
  flex-direction: column;
  padding: 9px 12px;
  border: 1px solid #c9d5e6;
  background: #f4f7fb;
}

.layer.side b {
  width: auto;
}

.layer.side span {
  font-size: 12px;
}

.seq td:first-child {
  width: 32px;
  text-align: center;
  font-weight: 700;
  color: #1a5fa8;
}

.seq td:nth-child(2) {
  width: 120px;
  white-space: nowrap;
  color: #1f3a66;
}

.note {
  margin: 10px 0;
  padding: 9px 12px;
  background: #eef3fa;
  border-left: 3px solid #1a5fa8;
  font-size: 13px;
  color: #344054;
}

.warn {
  color: #b42318;
}

.sev {
  display: inline-block;
  padding: 0 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.sev.high {
  background: #fde8e8;
  color: #b42318;
}

.sev.medium {
  background: #fff4e0;
  color: #b54708;
}

.stale {
  padding: 0 6px;
  background: #fff4e0;
  color: #b54708;
  font-size: 12px;
}

.faq dt {
  margin-top: 14px;
  font-weight: 700;
  color: #1f3a66;
}

.faq dt::before {
  content: 'Q. ';
  color: #1a5fa8;
}

.faq dd {
  margin: 4px 0 0;
  padding-left: 22px;
  color: #344054;
}
</style>
