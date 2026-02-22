import React from "react";

interface IconProps {
	className?: string;
	style?: React.CSSProperties;
	color?: string;
}

export const IncidentMapIcon: React.FC<IconProps> = ({
	className,
	style,
	color = "#d6455d",
}) => {
	return (
		<svg
			width="52"
			height="54"
			viewBox="0 0 52 54"
			fill="none"
			xmlns="http://www.w3.org/2000/svg"
			className={className}
			style={style}
		>
			<path
				d="M47.667 40H4.33301L26 1.02832L47.667 40Z"
				fill={color}
				stroke={color}
			/>
			<path
				d="M26 14.4858L36.6675 32.9167H15.3325L26 14.4858ZM26 8.83334L10.4167 35.75H41.5834L26 8.83334ZM27.4167 28.6667H24.5834V31.5H27.4167V28.6667ZM27.4167 20.1667H24.5834V25.8333H27.4167V20.1667Z"
				fill="white"
			/>
		</svg>
	);
};
