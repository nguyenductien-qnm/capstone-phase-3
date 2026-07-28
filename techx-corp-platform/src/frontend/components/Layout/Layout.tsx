import Header from '../Header';
import Footer from '../Footer';

interface IProps {
  children: React.ReactNode;
}

const Layout = ({ children }: IProps) => (
  <div className="flex min-h-screen flex-col bg-background text-foreground font-sans">
    <Header />
    <main className="flex-1">{children}</main>
    <Footer />
  </div>
);

export default Layout;
