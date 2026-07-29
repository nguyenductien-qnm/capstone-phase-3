import styled, { keyframes } from 'styled-components';
import RouterLink from 'next/link';

const shimmer = keyframes`
  0% { background-position: 200% center; }
  100% { background-position: -200% center; }
`;

export const AdContainer = styled.section`
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 48px auto;
  max-width: 800px;
  padding: 3px;
  border-radius: 20px;
  background: linear-gradient(90deg, #ff8a00, #e52e71, #9c27b0, #ff8a00);
  background-size: 200% auto;
  animation: ${shimmer} 5s linear infinite;
  box-shadow: 0 10px 30px -10px rgba(229, 46, 113, 0.4);
  transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.3s ease;

  &:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 20px 40px -15px rgba(229, 46, 113, 0.6);
  }
`;

export const AdContent = styled.div`
  width: 100%;
  padding: 32px 48px;
  background: #ffffff;
  border-radius: 17px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;

  @media (prefers-color-scheme: dark) {
    background: #0f172a;
  }
`;

export const AdText = styled.p`
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: linear-gradient(90deg, #e52e71, #ff8a00);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  cursor: pointer;
`;

export const Link = styled(RouterLink)`
  text-decoration: none;
  display: block;
  width: 100%;
`;
