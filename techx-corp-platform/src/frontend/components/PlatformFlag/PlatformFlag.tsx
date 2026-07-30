// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { NEXT_PUBLIC_PLATFORM = 'local' } = typeof window !== 'undefined' ? window.ENV : {};

const platform = NEXT_PUBLIC_PLATFORM;

const PlatformFlag = () => {
  return (
    <div className="absolute bottom-0 right-0 w-[100px] h-[27px] flex justify-center items-center text-xs lg:text-sm font-normal text-white bg-[#F4A810] lg:w-[190px] lg:h-[50px]">
      {platform}
    </div>
  );
};

export default PlatformFlag;
