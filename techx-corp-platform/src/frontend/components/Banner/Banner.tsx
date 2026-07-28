import Link from 'next/link';

const Banner = () => (
  <section className="relative flex h-[320px] items-center justify-center overflow-hidden bg-gradient-to-r from-slate-900 to-blue-900 text-white">
    <div className="absolute inset-0 bg-[url(/images/banner-telescope.jpg)] bg-cover bg-center opacity-30" />
    <div className="relative z-10 mx-auto max-w-7xl px-4 text-center">
      <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl lg:text-5xl">
        The best telescopes to see the world closer
      </h1>
      <Link href="#hot-products"
        className="mt-6 inline-block rounded-lg bg-white px-8 py-3 text-lg font-bold text-slate-900 transition hover:bg-gray-100">
        Go Shopping
      </Link>
    </div>
  </section>
);

export default Banner;
