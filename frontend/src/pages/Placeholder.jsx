import TopBar from '../components/TopBar';

export default function Placeholder({ title, glyph, note }) {
  return (
    <>
      <TopBar title={title} />
      <div className="screen-pad" style={{ paddingTop: 60, textAlign: 'center' }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 84,
          color: 'var(--ink)',
          opacity: 0.18,
          lineHeight: 1,
          marginBottom: 20,
        }}>{glyph}</div>
        <p style={{
          fontFamily: 'var(--font-ui)',
          fontSize: 13.5,
          color: 'var(--ink-soft)',
          lineHeight: 1.6,
        }}>{note}</p>
      </div>
    </>
  );
}
