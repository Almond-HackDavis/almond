import SwiftUI

extension Font {
    static func poppins(_ weight: PoppinsWeight, size: CGFloat) -> Font {
        .custom(weight.fontName, size: size)
    }

    enum PoppinsWeight {
        case regular, medium, semiBold, bold, extraBold
        case lightItalic, mediumItalic

        var fontName: String {
            switch self {
            case .regular:      return "Poppins-Regular"
            case .medium:       return "Poppins-Medium"
            case .semiBold:     return "Poppins-SemiBold"
            case .bold:         return "Poppins-Bold"
            case .extraBold:    return "Poppins-ExtraBold"
            case .lightItalic:  return "Poppins-LightItalic"
            case .mediumItalic: return "Poppins-MediumItalic"
            }
        }
    }
}
