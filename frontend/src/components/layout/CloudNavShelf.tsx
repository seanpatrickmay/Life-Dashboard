import { ReactNode } from 'react';
import styled from 'styled-components';
import { Z_LAYERS } from '../../styles/zLayers';

type Props = {
  children: ReactNode;
};

const ShelfWrap = styled.div`
  position: relative;
  width: 100%;
  display: flex;
  justify-content: center;
  margin-bottom: clamp(12px, 2vh, 28px);
  z-index: ${Z_LAYERS.nav};
`;

const Content = styled.div`
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
`;

export function CloudNavShelf({ children }: Props) {
  return (
    <ShelfWrap>
      <Content>{children}</Content>
    </ShelfWrap>
  );
}
