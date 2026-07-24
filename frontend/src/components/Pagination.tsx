import { ChevronLeft, ChevronRight, SkipBack, SkipForward } from 'lucide-react';

interface PaginationProps {
  current: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  /** 加载中时禁用翻页与每页条数切换 */
  disabled?: boolean;
}

export default function Pagination({ 
  current, 
  total, 
  pageSize, 
  onChange,
  onPageSizeChange,
  pageSizeOptions = [5, 10, 20, 50],
  disabled = false,
}: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(current, pages);

  const getPageNumbers = () => {
    const pageNumbers: (number | string)[] = [];
    
    if (pages <= 7) {
      for (let i = 1; i <= pages; i++) {
        pageNumbers.push(i);
      }
    } else {
      if (currentPage <= 4) {
        pageNumbers.push(1, 2, 3, 4, 5, '...', pages);
      } else if (currentPage >= pages - 3) {
        pageNumbers.push(1, '...', pages - 4, pages - 3, pages - 2, pages - 1, pages);
      } else {
        pageNumbers.push(1, '...', currentPage - 1, currentPage, currentPage + 1, '...', pages);
      }
    }
    
    return pageNumbers;
  };

  const handlePrev = () => {
    if (!disabled && currentPage > 1) {
      onChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (!disabled && currentPage < pages) {
      onChange(currentPage + 1);
    }
  };

  const handleFirst = () => {
    if (!disabled && currentPage > 1) {
      onChange(1);
    }
  };

  const handleLast = () => {
    if (!disabled && currentPage < pages) {
      onChange(pages);
    }
  };

  const navDisabled = disabled || currentPage <= 1;
  const nextDisabled = disabled || currentPage >= pages;

  return (
    <div className={`flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200 sm:px-6 ${disabled ? 'opacity-70' : ''}`}>
      <div className="flex-1 flex justify-between sm:hidden">
        <button
          onClick={handlePrev}
          disabled={navDisabled}
          className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          上一页
        </button>
        <button
          onClick={handleNext}
          disabled={nextDisabled}
          className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          下一页
        </button>
      </div>
      <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <p className="text-sm text-gray-700">
            显示第{' '}
            <span className="font-medium">
              {Math.min((currentPage - 1) * pageSize + 1, total)} - {Math.min(currentPage * pageSize, total)}
            </span>{' '}
            条，共{' '}
            <span className="font-medium">{total}</span>{' '}
            条记录
          </p>
          {onPageSizeChange && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">每页显示:</span>
              <select
                value={pageSize}
                disabled={disabled}
                onChange={(e) => onPageSizeChange(Number(e.target.value))}
                className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {pageSizeOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div>
          <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
            <button
              onClick={handleFirst}
              disabled={navDisabled}
              className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <SkipBack className="w-4 h-4" />
            </button>
            <button
              onClick={handlePrev}
              disabled={navDisabled}
              className="relative inline-flex items-center px-2 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            {getPageNumbers().map((page, index) => (
              typeof page === 'number' ? (
                <button
                  key={index}
                  onClick={() => !disabled && onChange(page)}
                  disabled={disabled}
                  className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium disabled:cursor-not-allowed ${
                    page === currentPage
                      ? 'z-10 bg-indigo-600 border-indigo-600 text-white'
                      : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  {page}
                </button>
              ) : (
                <span key={index} className="relative inline-flex items-center px-2 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-400">
                  ...
                </span>
              )
            ))}
            <button
              onClick={handleNext}
              disabled={nextDisabled}
              className="relative inline-flex items-center px-2 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              onClick={handleLast}
              disabled={nextDisabled}
              className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <SkipForward className="w-4 h-4" />
            </button>
          </nav>
        </div>
      </div>
    </div>
  );
}
