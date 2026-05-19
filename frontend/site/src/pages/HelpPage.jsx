import SiteHeader from "../components/SiteHeader.jsx";

/** lines: 블록 안 줄(줄간격만). 블록 사이는 넓은 간격 */
const SECTIONS = [
  {
    id: "intro",
    nodeId: "245:383",
    cardNodeId: "245:350",
    title: "소개",
    blocks: [
      {
        lines: [
          "Orangebeats는 아주대학교 파란학기제 도전팀 “오렌지카라멜”의 프로젝트 서비스입니다.",
          "설명란, 댓글, 영상 내부 요인 분석을 통해 Youtube에서 음원을 추출하고, 이를 Spotify에 매칭해 플레이리스트를 생성합니다.",
        ],
      },
    ],
  },
  {
    id: "logic",
    nodeId: "245:385",
    cardNodeId: "245:387",
    title: "로직 소개",
    blocks: [
      {
        lines: [
          "Orangebeats는 영상 속 노래 정보를 한 번에 확정하지 않고, 가장 가벼운 방법부터 순서대로 확인합니다.",
        ],
      },
      {
        lines: [
          "먼저 Youtube 영상의 제목, 설명란, 댓글, 타임스탬프 처럼 텍스트로 확인할 수 있는 정보를 분석합니다.",
          "여기서 곡명과 아티스트가 충분히 추출되면 바로 Spotify에서 매칭합니다.",
        ],
      },
      {
        lines: [
          "텍스트 정보가 부족하거나 형식이 불규칙 한 경우에는, OCR, ACR 분석을 진행합니다.",
          "OCR은 영상 화면에 보이는 자막, 곡 제목, 아티스트명, 타임스탬프 등을 읽어 노래 후보를 찾는 방식입니다.",
          "ACR은 영상의 일부 오디오를 분석해 실제 들리는 음악을 식별하는 방식으로, 텍스트나 화면 정보가 부족한 영상에서도 노래를",
          "찾는데 도움을 줍니다.",
        ],
      },
      {
        lines: [
          "즉, Orangebeats는 텍스트 분석 -> OCR분석, ACR 분석 순서로 필요한 만큼만 분석해서 노래 매칭률을 높입니다.",
        ],
      },
    ],
  },
  {
    id: "tips",
    nodeId: "245:394",
    cardNodeId: "245:392",
    title: "이용 팁",
    blocks: [
      {
        lines: [
          "현재 Spotify와 공개 메타데이터 기반으로 곡을 매칭하고 있어,",
          "일반적으로 해외 음원이나 정보가 많이 등록된 곡일수록 매칭의 정확도가 높습니다.",
        ],
      },
      {
        lines: ["반면 아래와 같은 경우에는 일부 곡이 정확히 인식되지 않을 수 있습니다."],
      },
      {
        lines: [
          "인디·비공식 음원",
          "아티스트명·곡명 표기가 일정하지 않은 경우",
          "Spotify 등록 정보가 부족한 경우 등",
        ],
      },
      {
        lines: [
          "특히 영어권 음원은 공개 데이터와 메타데이터가 풍부해 비교적 안정적으로 매칭되는 편이며,",
          "국내 인디 음원이나 비주류 곡은 현재도 매칭 로직을 지속적으로 개선하고 있습니다.",
        ],
      },
    ],
  },
];

export default function HelpPage() {
  return (
    <div className="help-page" data-node-id="245:338" data-name="001_1_QNA">
      <SiteHeader />
      <main className="help-page__main">
        <h1 className="help-page__title" data-node-id="245:339">
          Help
        </h1>

        <div className="help-page__sections">
          {SECTIONS.map((section) => (
            <section
              key={section.id}
              className="help-page__section"
              aria-labelledby={`help-section-${section.id}`}
            >
              <h2
                id={`help-section-${section.id}`}
                className="help-page__section-title"
                data-node-id={section.nodeId}
              >
                {section.title}
              </h2>
              <div className="help-page__card" data-node-id={section.cardNodeId}>
                {section.blocks.map((block, blockIndex) => (
                  <div key={`${section.id}-block-${blockIndex}`} className="help-page__card-block">
                    {block.lines.map((line, lineIndex) => (
                      <p key={`${section.id}-${blockIndex}-${lineIndex}`} className="help-page__card-text">
                        {line}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
