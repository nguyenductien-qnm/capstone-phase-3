// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import Link from 'next/link';

const Ad = () => {
  const { adList } = useAd();
  const { text, redirectUrl } = adList[Math.floor(Math.random() * adList.length)] || { text: '', redirectUrl: '' };

  if (!text) return null;

  return (
    <section 
      className="relative flex items-center justify-center my-12 mx-auto max-w-[800px] p-[3px] rounded-[20px] bg-gradient-to-r from-[#ff8a00] via-[#e52e71] to-[#ff8a00] bg-[length:200%_auto] animate-[shimmer_5s_linear_infinite] shadow-[0_10px_30px_-10px_rgba(229,46,113,0.4)] transition-all duration-300 ease-[cubic-bezier(0.175,0.885,0.32,1.275)] hover:-translate-y-1 hover:scale-[1.02] hover:shadow-[0_20px_40px_-15px_rgba(229,46,113,0.6)]" 
      data-cy={CypressFields.Ad}
    >
      <Link href={redirectUrl} className="no-underline block w-full">
        <div className="w-full py-8 px-12 bg-white dark:bg-slate-900 rounded-[17px] text-center flex items-center justify-center">
          <p className="m-0 text-xl font-extrabold tracking-tight bg-gradient-to-r from-[#e52e71] to-[#ff8a00] bg-clip-text text-transparent cursor-pointer">
            {text}
          </p>
        </div>
      </Link>
    </section>
  );
};

export default Ad;
