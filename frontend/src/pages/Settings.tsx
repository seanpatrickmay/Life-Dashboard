import styled from 'styled-components';

const Card = styled.div`
  background: rgba(255, 255, 255, 0.85);
  border-radius: 24px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
`;

export function SettingsPage() {
  return (
    <Card>
      <h2>Settings</h2>
      <p>Customize update cadence and display preferences.</p>
    </Card>
  );
}
