import InfoPage from "../components/InfoPage.jsx";

export default function ContactPage() {
  return (
    <InfoPage
      title="Contact us"
      description="서비스 개선 제안, 오류 제보, 협업 문의를 남겨주세요."
    >
      <ul className="site-info__list">
        <li>Playlist Lab의 QA 게시판에서도 질문과 버그를 남길 수 있습니다.</li>
        <li>긴급한 로그인·연동 문제는 Spotify 연동 상태와 함께 문의해주세요.</li>
        <li>기능 제안은 사용하신 YouTube URL 예시를 함께 적어주시면 검토가 빠릅니다.</li>
      </ul>
    </InfoPage>
  );
}
