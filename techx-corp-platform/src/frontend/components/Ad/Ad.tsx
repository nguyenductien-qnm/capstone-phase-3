// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import * as S from './Ad.styled';

const Ad = () => {
  const { adList } = useAd();
  const { text, redirectUrl } = adList[Math.floor(Math.random() * adList.length)] || { text: '', redirectUrl: '' };

  if (!text) return null;

  return (
    <S.AdContainer data-cy={CypressFields.Ad}>
      <S.Link href={redirectUrl}>
        <S.AdContent>
          <S.AdText>{text}</S.AdText>
        </S.AdContent>
      </S.Link>
    </S.AdContainer>
  );
};

export default Ad;
