// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Header from '../Header';
import Footer from '../Footer';

interface IProps {
  children: React.ReactNode;
}

const Layout = ({ children }: IProps) => {
  return (
    <div className="flex flex-col flex-1 min-h-screen">
      <Header />
      <main className="flex-1 w-full flex flex-col overflow-x-hidden max-w-full">{children}</main>
      <Footer />
    </div>
  );
};

export default Layout;

