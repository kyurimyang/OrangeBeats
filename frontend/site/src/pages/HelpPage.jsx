import InfoPage from "../components/InfoPage.jsx";

export default function HelpPage() {
  return (
    <InfoPage
      title="Help"
      description="YouTube URL을 붙여넣고 Spotify 후보를 확인한 뒤 플레이리스트를 만드는 흐름을 안내합니다."
    >
      <ol className="site-info__list">
        <li>홈에서 Spotify 연동하기를 눌러 계정을 연결합니다.</li>
        <li>Playlist Lab에서 YouTube URL을 입력하고 분석 모드를 선택합니다.</li>
        <li>추출된 후보를 확인한 뒤 원하는 곡만 선택해 플레이리스트를 생성합니다.</li>
      </ol>
    </InfoPage>
  );
}
