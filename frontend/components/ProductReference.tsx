'use client';
type Props={product:Record<string,any>;required:boolean;busy:boolean;onUpload:(file:File)=>void;onEdit:()=>void};
export default function ProductReference({product,required,busy,onUpload,onEdit}:Props){
 const images=product.images||[];
 return <section className="product-reference" aria-label="Product reference images">
  <strong>{images.length?'Product reference image ready':required?'Product image required':'No product reference image'}</strong>
  <p>{images.length?'The first image is the reference used by Product Accuracy Mode.':required?'Upload a product photo you own or are authorized to use before creating this project. Fetch Information does not import product images.':'Without a reference image, AI-generated product appearance may differ from the actual product.'}</p>
  {!!images.length&&<img src={'/api/images/'+images[0]} alt={'Product reference for '+product.name}/>}
  <div className="row wrap"><label className="button">{images.length?'Add Another Image':'Upload Product Image'}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy||images.length>=20} onChange={e=>{const file=e.target.files?.[0];e.currentTarget.value='';if(file)onUpload(file)}} hidden/></label><button type="button" disabled={busy} onClick={onEdit}>Manage Product Images</button></div>
  <small>JPEG, PNG or WebP. Maximum 12 MB per image.</small>
  {!images.length&&required&&<small>For a concept video without a product reference, turn off Product Accuracy Mode below. Product appearance may differ.</small>}
 </section>
}
