import styled from 'styled-components';
import { FoodManager } from '../components/nutrition/FoodManager';

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.5vw, 22px);
  margin-top: clamp(16px, 4vh, 48px);
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
`;

export function FoodManagerPage() {
  return (
    <Page>
      <Title>Food Database</Title>
      <FoodManager />
    </Page>
  );
}
