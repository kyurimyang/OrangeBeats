import InfoPage from "../components/InfoPage.jsx";

export default function FaqPage() {
  return (
    <InfoPage
      title="FAQ"
      description="자주 묻는 질문을 모았습니다. 추가 문의는 Contact us 페이지를 이용해주세요."
    >
      <dl className="site-info__faq">
        <div>
          <dt>text, OCR, ACR 차이는 무엇인가요?</dt>
          <dd>text는 설명·댓글 기반 추출, OCR은 영상 자막·화면 텍스트, ACR은 음원 인식 기반 후보를 찾습니다.</dd>
        </div>
        <div>
          <dt>플레이리스트는 자동으로 생성되나요?</dt>
          <dd>후보를 먼저 보여주고, 사용자가 선택한 곡만 Spotify 플레이리스트에 담습니다.</dd>
        </div>
        <div>
          <dt>매칭이 안 되는 곡이 있으면 어떻게 하나요?</dt>
          <dd>후보 화면에서 다른 검색 결과를 고르거나, 해당 곡을 제외한 뒤 다시 생성할 수 있습니다.</dd>
        </div>
      </dl>
    </InfoPage>
  );
}
